# YouTube search without an API key

This container runs `yt-dlp` searches and returns video IDs, titles and channel names. The frontend still uses YouTube's official embedded player. There is no video download, stream proxy, Jellyfin access or Tesla integration.

## Deploy with Coolify at mobile.oqen.pt

1. Point the DNS A record for `mobile.oqen.pt` to your VPS (and ensure any AAAA record points to a working IPv6 address on it). The Coolify proxy needs reachable ports 80/443 for routing and TLS.
2. In Coolify, add an application from `https://github.com/andrenunesjob/TeslaMediaCenter`, selecting branch **gh-pages**. These files are on that branch, not main.
3. Select **Dockerfile** as the build pack. Set **Base Directory** to `/youtube-search` and **Dockerfile Location** to `/Dockerfile` (relative to that base/build context).
4. Set the domain to **https://mobile.oqen.pt** and the application's internal/exposed port to **8080**. Use the Coolify proxy; do not add a public host-port mapping.
5. Set the runtime environment variable `ALLOWED_ORIGINS=https://andrenunesjob.github.io`. This is an origin: do not append `/TeslaMediaCenter/` or a trailing slash. No API key is required.
6. Set the HTTP health check to `GET /health`, port `8080`, expected status `200`. If your reverse proxy has a response timeout, allow at least 30 seconds.
7. Deploy. The Dockerfile supplies a non-root user and its own health check. You can set a 256 MB memory limit and 1 CPU in Coolify; these are also shown in the standalone Compose example.
8. Verify from a terminal:

   ```sh
   curl --fail-with-body https://mobile.oqen.pt/health
   curl --fail-with-body -G https://mobile.oqen.pt/api/search \
     --data-urlencode 'q=lofi music' \
     -H 'Origin: https://andrenunesjob.github.io'
   ```

   The first response should be `{"status":"ok"}`. The second must contain a nonempty `items` array to establish real search readiness. A successful health check only proves the service is running.

9. Refresh the GitHub Pages site and check for version **2.0.4** in the footer. Under **Definições de pesquisa YouTube**, the search service defaults to `https://mobile.oqen.pt`. Leave the optional YouTube API key blank. A custom service address is remembered only in that browser.

If Coolify cannot access the repository, use its normal GitHub connection; do not put a GitHub token in the Dockerfile. If its Dockerfile path fields behave differently in your version, the required build context is the repository's `youtube-search` directory and the Dockerfile is inside that directory.

## Behaviour and limits

- `GET /api/search?q=...`: queries of 2–200 characters; at most 12 results.
- Responses use `{ "items": [{ "id": "...", "title": "...", "channel": "...", "thumb": "..." }] }`.
- Five-minute bounded in-memory cache, one active upstream search, 60 requests per minute globally. HTTP 429 includes `Retry-After`; these limits reset on restart.
- The service only invokes the fixed `ytsearch12:` extractor. It does not accept arbitrary target URLs, serve arbitrary HTTP requests, use a shell, or load yt-dlp config/cookies.
- Browser access is limited by `ALLOWED_ORIGINS` (comma-separated). CORS is not authentication: non-browser clients can still call the public endpoint. For a private installation, add authentication/rate limits at the proxy as needed; don't put private access credentials in the public HTML.
- Outbound HTTPS to YouTube is required. YouTube may throttle or reject searches from datacenter IPs. A blocked IP can still prevent this approach from working; moving a backend does not guarantee search availability. Update the pinned `yt-dlp` version when extractor fixes are required, then redeploy.
- Errors use HTTP 400/403/405/429/502/504 and a JSON `error` message. A 502 from the service means extraction failed; an HTML gateway page usually means the Coolify domain/route is incorrect. The frontend retains a direct YouTube search link on failure.
- No user-provided API key is needed, but the extractor uses YouTube's unofficial search interfaces. There is no guarantee of availability or embed permission for every result. Video playback restrictions remain YouTube's responsibility.

## Standalone Docker alternative

From this directory:

```sh
docker compose up -d --build
curl --fail-with-body http://127.0.0.1:8787/health
```

The supplied Compose file binds the service only to the VPS loopback port 8787. Put an HTTPS reverse proxy in front of it. A proxy in a separate container needs a shared Docker network to reach the service on port 8080; its own `localhost` does not refer to this container. For Coolify, use the application instructions above instead of the standalone port mapping.

## Local verification

From the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The service unit tests exercise validation, CORS, caching, limits, subprocess arguments and error handling using simulated extraction. The browser tests require Playwright and Chromium. A real search from the deployed VPS is still required, because these tests cannot establish whether YouTube permits that VPS IP.
