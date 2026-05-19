import json
from datetime import datetime
from typing import Generator, Any

import anthropic

SYSTEM_PROMPT = """Je bent een audit-analist. Je taak is om uit historische audit-documenten een beknopt overzicht te maken van welke bevindingen relevant zijn voor de huidige audit.

Analyseer de aangeleverde documenten en bepaal:
1. Welke bevindingen uit welke audits relevant zijn voor de huidige audit (op basis van opdrachtbrief en/of zoektermen als die zijn opgegeven, anders op basis van de inhoud).
2. Aanvullende aandachtspunten die belangrijk zijn voor de auditor.

Temporele weging: bevindingen van 0-2 jaar geleden wegen zwaarder dan 3-5 jaar, en 6+ jaar zijn alleen relevant als ze structureel/terugkerend zijn.

Retourneer ALLEEN een geldig JSON object, zonder markdown, zonder uitleg:

{"bevindingen":[{"bron":"bestandsnaam.pdf","jaar":"2023","bevinding":"Concrete beschrijving van de bevinding","relevantie":"Waarom dit relevant is voor de huidige audit","prioriteit":"Hoog|Middel|Laag"}],"aandachtspunten":[{"onderwerp":"Naam van het aandachtspunt","toelichting":"Wat de auditor moet weten of controleren"}],"samenvatting":"Korte samenvatting in 2-3 zinnen van het totaalbeeld","metadata":{"bestanden_geanalyseerd":0,"kijktermijn_jaren":0,"analysedatum":""}}"""


class AuditAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze_stream(
        self,
        extracted_files: list[dict],
        lookback_years: int,
        engagement_data: dict | None = None,
        keywords: str = '',
    ) -> Generator[dict[str, Any], None, None]:
        """Stream analyse-events als dict objecten."""

        content = self._build_content(extracted_files, lookback_years,
                                       engagement_data=engagement_data,
                                       keywords=keywords)
        full_text = ''

        try:
            with self.client.messages.stream(
                model='claude-opus-4-6',
                max_tokens=4096,
                thinking={'type': 'adaptive'},
                output_config={'effort': 'medium'},
                system=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': content}],
            ) as stream:
                thinking_active = False

                for event in stream:
                    etype = getattr(event, 'type', None)

                    if etype == 'content_block_start':
                        block = getattr(event, 'content_block', None)
                        if block:
                            if block.type == 'thinking':
                                thinking_active = True
                                yield {'type': 'thinking_start',
                                       'message': 'Claude analyseert de documenten diepgaand...'}
                            elif block.type == 'text':
                                thinking_active = False
                                yield {'type': 'text_start',
                                       'message': 'Rapport wordt gegenereerd...'}

                    elif etype == 'content_block_delta':
                        delta = getattr(event, 'delta', None)
                        if delta:
                            if delta.type == 'thinking_delta':
                                # Stuur een korte samenvatting van het denken
                                snippet = getattr(delta, 'thinking', '')[:120]
                                if snippet:
                                    yield {'type': 'thinking', 'text': snippet}
                            elif delta.type == 'text_delta':
                                chunk = getattr(delta, 'text', '')
                                full_text += chunk
                                yield {'type': 'token', 'text': chunk}

                # ── Parseer JSON uit de gegenereerde tekst ──────────────
                import re
                text = full_text.strip()

                # Strip markdown code fences als Claude ze toch gebruikt
                fence_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.DOTALL)
                if fence_match:
                    text = fence_match.group(1)

                json_start = text.find('{')
                json_end = text.rfind('}') + 1

                if json_start == -1 or json_end <= json_start:
                    yield {
                        'type': 'error',
                        'message': 'Geen geldig JSON gevonden in Claude-respons.',
                        'raw': full_text[:800],
                    }
                    return

                report_data = json.loads(text[json_start:json_end])

                # Metadata aanvullen
                report_data.setdefault('metadata', {})
                report_data['metadata']['bestanden_geanalyseerd'] = len(extracted_files)
                report_data['metadata']['kijktermijn_jaren'] = lookback_years
                report_data['metadata']['analysedatum'] = datetime.now().strftime('%d-%m-%Y')

                yield {'type': 'complete', 'report': report_data}

        except anthropic.AuthenticationError:
            yield {'type': 'error',
                   'message': 'Ongeldige API key. Controleer je Claude API key.'}
        except anthropic.RateLimitError:
            yield {'type': 'error',
                   'message': 'Rate limit bereikt. Probeer het later opnieuw.'}
        except anthropic.BadRequestError as exc:
            yield {'type': 'error', 'message': f'Verzoek fout: {exc}'}
        except json.JSONDecodeError as exc:
            yield {'type': 'error',
                   'message': f'JSON-parse fout: {exc}',
                   'raw': full_text[:800]}
        except Exception as exc:
            import traceback
            yield {'type': 'error',
                   'message': str(exc),
                   'detail': traceback.format_exc()[-600:]}

    # ──────────────────────────────────────────────────────────────────── #
    #  Content builder                                                      #
    # ──────────────────────────────────────────────────────────────────── #

    def _build_content(
        self,
        extracted_files: list[dict],
        lookback_years: int,
        engagement_data: dict | None = None,
        keywords: str = '',
    ) -> list[dict]:
        content: list[dict] = []

        # ── Tekst-blok: parameters + optionele context ────────────────── #
        parts = [
            f'ANALYSE PARAMETERS\n'
            f'══════════════════\n'
            f'Kijktermijn : {lookback_years} jaar\n'
            f'Datum       : {datetime.now().strftime("%d-%m-%Y")}\n'
            f'Bestanden   : {len(extracted_files)}\n\n',
        ]

        # ── Opdrachtbrief (engagement letter) ─────────────────────────── #
        if engagement_data and engagement_data.get('text'):
            parts.append(
                'OPDRACHTBRIEF — AUDITSCOPE (BEPALEND VOOR REIKWIJDTE)\n'
                '═══════════════════════════════════════════════════════\n'
                'De onderstaande tekst is de officiële opdrachtbrief van de huidige audit.\n'
                'Gebruik dit als primaire lens bij het analyseren van de historische documenten.\n'
                'Bevindingen die direct relevant zijn voor deze scope krijgen hogere prioriteit.\n'
                'Bevindingen buiten deze scope kunnen worden gesignaleerd maar label ze als "buiten scope".\n\n'
                + engagement_data['text']
                + '\n\n'
            )

        # ── Zoektermen / keywords ──────────────────────────────────────── #
        if keywords:
            parts.append(
                'ZOEKTERMEN VAN DE AUDITOR\n'
                '═════════════════════════\n'
                'De auditor heeft de volgende zoektermen opgegeven. Besteed expliciet\n'
                'aandacht aan historische bevindingen, patronen en risico\'s die verband\n'
                'houden met deze termen:\n\n'
                + keywords
                + '\n\n'
            )

        parts.append(
            'GEËXTRAHEERDE HISTORISCHE AUDIT-DOCUMENTEN\n'
            '══════════════════════════════════════════\n\n'
        )

        for fd in extracted_files:
            fname = fd.get('filename', 'onbekend')
            ftype = fd.get('type', '').upper()
            text = fd.get('text', '')
            meta = fd.get('metadata', {})

            header = f'┌─ BESTAND: {fname} [{ftype}]'
            if meta.get('pages'):
                header += f' — {meta["pages"]} pagina\'s'
            elif meta.get('slides'):
                header += f' — {meta["slides"]} slides'
            elif meta.get('sheets'):
                header += f' — tabbladen: {", ".join(str(s) for s in meta["sheets"])}'

            if fd.get('error'):
                parts.append(f'{header}\n[FOUT: {fd["error"]}]\n\n')
            elif fd.get('is_scan'):
                parts.append(f'{header}\n[PDF scan — minimale tekst extraheerbaar]\n\n')
            elif text:
                parts.append(f'{header}\n{text}\n\n')

        content.append({'type': 'text', 'text': '\n'.join(parts)})

        # ── Afbeeldings-blokken ────────────────────────────────────────── #
        img_count = 0
        for fd in extracted_files:
            img_data = fd.get('image_data')
            if img_data and img_count < 8:
                content.append({
                    'type': 'text',
                    'text': f'\n[Visuele analyse van: {fd["filename"]}]',
                })
                content.append({
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': img_data['media_type'],
                        'data': img_data['base64'],
                    },
                })
                img_count += 1

        # ── Instructie ──────────────────────────────────────────────────── #
        scope_note = ''
        if engagement_data:
            scope_note += ' Gebruik de opdrachtbrief als leidraad voor de reikwijdte.'
        if keywords:
            scope_note += f' Zoektermen "{keywords}" krijgen extra aandacht.'

        content.append({
            'type': 'text',
            'text': (
                f'\nGenereer nu het bevindingenoverzicht als JSON '
                f'voor een kijktermijn van {lookback_years} jaar.{scope_note} '
                'Begin direct met {{ en eindig met }}. Geen markdown, geen uitleg, alleen raw JSON.'
            ),
        })

        return content
