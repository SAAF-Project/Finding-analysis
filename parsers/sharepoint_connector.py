import os
from typing import Callable

SUPPORTED_EXTENSIONS = {'.pdf', '.pptx', '.xlsx', '.xls', '.docx',
                        '.png', '.jpg', '.jpeg', '.gif', '.webp'}


class SharePointConnector:
    """Downloads files from a SharePoint folder to a local directory."""

    def fetch_files(
        self,
        site_url: str,
        folder_path: str,
        username: str,
        password: str,
        download_dir: str,
        progress_cb: Callable[[str], None] | None = None,
    ) -> list[str]:
        """
        Connect to SharePoint, list files in `folder_path`, download the
        supported ones to `download_dir`, and return their local paths.

        `progress_cb` is an optional callable(msg: str) used to emit status
        messages back to the SSE stream.
        """
        from office365.sharepoint.client_context import ClientContext
        from office365.runtime.auth.user_credential import UserCredential

        def _log(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)

        _log(f'Verbinden met {site_url} ...')
        ctx = ClientContext(site_url).with_credentials(
            UserCredential(username, password)
        )

        # Verify connection
        web = ctx.web
        ctx.load(web)
        ctx.execute_query()
        _log(f'Verbonden met: {web.title}')

        # List files
        _log(f'Bestanden ophalen uit: {folder_path}')
        folder = ctx.web.get_folder_by_server_relative_url(folder_path)
        files = folder.files
        ctx.load(files)
        ctx.execute_query()

        supported = [f for f in files
                     if os.path.splitext(f.name)[1].lower() in SUPPORTED_EXTENSIONS]

        _log(f'{len(supported)} ondersteunde bestanden gevonden in SharePoint map')

        downloaded: list[str] = []
        for sp_file in supported:
            local_path = os.path.join(download_dir, sp_file.name)
            with open(local_path, 'wb') as fh:
                sp_file.download(fh)
            ctx.execute_query()
            _log(f'  ↓ {sp_file.name}')
            downloaded.append(local_path)

        return downloaded
