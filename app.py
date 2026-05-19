import os
import json
import uuid
from flask import Flask, render_template, request, Response, send_file, stream_with_context
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'pptx', 'xlsx', 'xls', 'docx', 'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sse_error(message: str) -> Response:
    return Response(
        f"data: {json.dumps({'type': 'error', 'message': message})}\n\n",
        mimetype='text/event-stream'
    )


@app.route('/')
def index():
    return render_template('index.html',
                           default_api_key=os.getenv('ANTHROPIC_API_KEY', ''))


@app.route('/analyze', methods=['POST'])
def analyze():
    # ── Collect form fields ──────────────────────────────────────────────
    api_key = request.form.get('api_key', '').strip()
    if not api_key:
        return sse_error('Claude API key is vereist')

    lookback_years = int(request.form.get('lookback_years', 3))
    keywords = request.form.get('keywords', '').strip()

    # SharePoint credentials (all four required together)
    sp_site_url = request.form.get('sp_site_url', '').strip()
    sp_folder   = request.form.get('sp_folder', '').strip()
    sp_username = request.form.get('sp_username', '').strip()
    sp_password = request.form.get('sp_password', '').strip()
    use_sharepoint = bool(sp_site_url and sp_folder and sp_username and sp_password)

    # Local files
    local_files = request.files.getlist('files[]')
    has_local = any(f and f.filename and allowed_file(f.filename) for f in local_files)

    if not has_local and not use_sharepoint:
        return sse_error('Upload minstens één bestand of geef een SharePoint-map op')

    # Engagement letter (optional, single file)
    engagement_file = request.files.get('engagement_letter')
    has_engagement = (engagement_file and engagement_file.filename and
                      allowed_file(engagement_file.filename))

    # ── Create upload directory ──────────────────────────────────────────
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOAD_FOLDER, upload_id)
    os.makedirs(upload_dir)

    # Save local audit files
    saved_paths: list[str] = []
    for file in local_files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            saved_paths.append(filepath)

    # Save engagement letter to a separate path
    engagement_path: str | None = None
    if has_engagement:
        ext = os.path.splitext(secure_filename(engagement_file.filename))[1].lower()
        engagement_path = os.path.join(upload_dir, f'_engagement_letter{ext}')
        engagement_file.save(engagement_path)

    # ── SSE generator ────────────────────────────────────────────────────
    def generate():
        from parsers.file_processor import FileProcessor
        from agent.audit_agent import AuditAgent
        from report.report_generator import ReportGenerator

        def progress(msg: str):
            return f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"

        try:
            processor = FileProcessor()

            # ── Step 1a: Download from SharePoint ─────────────────────
            if use_sharepoint:
                yield progress('Verbinding maken met SharePoint...')
                from parsers.sharepoint_connector import SharePointConnector

                sp_messages: list[str] = []

                def sp_cb(msg: str):
                    sp_messages.append(msg)

                try:
                    connector = SharePointConnector()
                    sp_paths = connector.fetch_files(
                        sp_site_url, sp_folder, sp_username, sp_password,
                        upload_dir, progress_cb=sp_cb
                    )
                    for msg in sp_messages:
                        yield progress(msg)
                    saved_paths.extend(sp_paths)
                    yield progress(f'{len(sp_paths)} bestanden opgehaald van SharePoint')
                except Exception as sp_err:
                    yield f"data: {json.dumps({'type': 'progress', 'message': f'⚠ SharePoint fout: {sp_err}. Doorgaan met lokale bestanden...'})}\n\n"

            if not saved_paths:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Geen bestanden beschikbaar voor analyse'})}\n\n"
                return

            # ── Step 1b: Parse audit files ─────────────────────────────
            yield progress(f'Bestanden verwerken ({len(saved_paths)} bestanden)...')
            extracted_data = processor.process_files(saved_paths)
            names = ', '.join(os.path.basename(p) for p in saved_paths[:5])
            if len(saved_paths) > 5:
                names += f' en {len(saved_paths) - 5} meer'
            yield progress(f'Verwerkt: {names}')

            # ── Step 1c: Parse engagement letter ──────────────────────
            engagement_data = None
            if engagement_path:
                yield progress('Opdrachtbrief verwerken...')
                engagement_data = processor.process_single_file(engagement_path)
                if engagement_data:
                    yield progress(f'Opdrachtbrief geladen: {os.path.basename(engagement_path)}')

            # ── Step 2: Claude analysis ────────────────────────────────
            ctx_parts = []
            if engagement_data:
                ctx_parts.append('opdrachtbrief')
            if keywords:
                ctx_parts.append('zoektermen')
            ctx_label = f' + {" & ".join(ctx_parts)}' if ctx_parts else ''
            yield progress(f'Claude AI analyse starten (GIAS 13.2{ctx_label})...')

            agent = AuditAgent(api_key)
            report_data = None

            for event in agent.analyze_stream(
                extracted_data, lookback_years,
                engagement_data=engagement_data,
                keywords=keywords,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                if event.get('type') == 'complete':
                    report_data = event.get('report')

            if not report_data:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Geen rapport data ontvangen van Claude'})}\n\n"
                return

            # ── Step 3: Generate reports ───────────────────────────────
            yield progress('HTML, Word en PDF rapport aanmaken...')
            generator = ReportGenerator()
            html_path = os.path.join(upload_dir, 'report.html')
            docx_path = os.path.join(upload_dir, 'report.docx')
            pdf_path  = os.path.join(upload_dir, 'report.pdf')
            generator.generate_html(report_data, html_path)
            generator.generate_docx(report_data, docx_path)
            generator.generate_pdf(report_data, pdf_path)

            yield f"data: {json.dumps({'type': 'done', 'upload_id': upload_id, 'report': report_data})}\n\n"

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'detail': tb[-500:]})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@app.route('/download/<upload_id>/<fmt>')
def download(upload_id, fmt):
    safe_id = secure_filename(upload_id)
    upload_dir = os.path.join(UPLOAD_FOLDER, safe_id)

    if not os.path.exists(upload_dir):
        return 'Rapport niet gevonden', 404

    if fmt == 'html':
        return send_file(os.path.join(upload_dir, 'report.html'),
                         as_attachment=True, download_name='audit_rapport.html')
    elif fmt == 'docx':
        return send_file(os.path.join(upload_dir, 'report.docx'),
                         as_attachment=True, download_name='audit_rapport.docx')
    elif fmt == 'pdf':
        return send_file(os.path.join(upload_dir, 'report.pdf'),
                         as_attachment=True, download_name='audit_rapport.pdf')

    return 'Ongeldig formaat', 400


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
