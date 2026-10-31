"""Browser regression checks. Run: python3 -m unittest discover -s tests -v"""
import json
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright, expect

HTML = (Path(__file__).resolve().parents[1] / 'index.html').read_text()
SITE = 'https://andrenunesjob.github.io/TeslaMediaCenter/'
SERVER = 'https://media.oqen.pt'


class Integrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.errors = []
        self.requests = []
        self.api_status = 200
        self.api_body = None
        self.auth_status = 200
        self.auth_body = {'AccessToken': 'test-token', 'User': {'Id': 'user-1', 'Name': 'Demo'}}
        self.views_status = 200
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.route('**/*', self.route)
        self.page.goto(SITE, wait_until='domcontentloaded')
        self.page.locator('summary').click()

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def route(self, route):
        request = route.request
        if request.url == SITE:
            route.fulfill(content_type='text/html', body=HTML)
        elif request.url.startswith('https://www.googleapis.com/youtube/v3/search?'):
            self.requests.append(request)
            route.fulfill(status=self.api_status, content_type='application/json', body=json.dumps(self.api_body or {'items': []}))
        elif request.url.startswith(SERVER):
            self.requests.append(request)
            if request.url.endswith('/Users/AuthenticateByName'):
                route.fulfill(status=self.auth_status, content_type='application/json', body=json.dumps(self.auth_body))
            elif request.url.endswith('/Views'):
                route.fulfill(status=self.views_status, content_type='application/json', body=json.dumps({'Items': [{'Id': 'movies', 'Name': 'Filmes', 'CollectionType': 'movies'}]}))
            else:
                route.fulfill(content_type='application/json', body=json.dumps({'Items': [{'Id': 'film', 'Name': 'Test film', 'ProductionYear': 2026}]}))
        else:
            route.abort()

    def login(self, url=SERVER):
        self.page.locator('.jelly-tab').click()
        self.page.locator('#jelly-server-url').fill(url)
        self.page.locator('#jelly-username').fill('demo')
        self.page.locator('#jelly-password').fill('test-password')
        self.page.locator('#jelly-connect-btn').click()
        expect(self.page.locator('#jelly-connect-btn')).to_be_enabled()

    def test_direct_youtube_links_skip_search(self):
        for value in ['dQw4w9WgXcQ', 'https://youtu.be/dQw4w9WgXcQ?t=12', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'https://www.youtube.com/shorts/dQw4w9WgXcQ', 'https://www.youtube.com/live/dQw4w9WgXcQ']:
            self.page.locator('#yt-search-input').fill(value)
            self.page.locator('#yt-search-btn').click()
            expect(self.page.locator('#yt-frame')).to_have_attribute('src', 'https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0&enablejsapi=1&autoplay=1&playsinline=1&origin=https%3A%2F%2Fandrenunesjob.github.io')
        self.assertEqual(self.requests, [])
        self.assertIsNone(self.page.evaluate("ytVideoId('https://example.com/watch?v=dQw4w9WgXcQ')"))
        expect(self.page.locator('#yt-frame')).to_have_attribute('referrerpolicy', 'strict-origin-when-cross-origin')

    def test_search_without_key_has_native_fallback(self):
        self.page.evaluate("window.open = (...args) => { window.openedSearch = args; }")
        expect(self.page.locator('#yt-search-btn')).to_contain_text('Pesquisar no YouTube')
        self.page.locator('#yt-search-input').fill('lofi & music')
        self.page.locator('#yt-search-btn').click()
        expect(self.page.locator('#yt-results a')).to_have_attribute('href', 'https://www.youtube.com/results?search_query=lofi%20%26%20music')
        self.assertEqual(self.page.evaluate('openedSearch'), ['https://www.youtube.com/results?search_query=lofi%20%26%20music', '_blank', 'noopener,noreferrer'])
        self.assertEqual(self.requests, [])

    def test_player_waits_for_ready_and_plays_latest_selection(self):
        self.page.evaluate('''() => {
            window.playedIds = [];
            window.YT = {Player: function(id, options) {
                window.playerEvents = options.events;
                this.loadVideoById = videoId => playedIds.push(videoId);
            }};
            onYouTubeIframeAPIReady();
        }''')
        src = self.page.locator('#yt-frame').get_attribute('src')
        self.page.evaluate("ytLoadDirect('dQw4w9WgXcQ'); ytLoadDirect('jfKfPfyJRdk')")
        self.assertEqual(self.page.evaluate('playedIds'), [])
        expect(self.page.locator('#yt-frame')).to_have_attribute('src', src)
        self.page.evaluate('playerEvents.onReady({target: ytPlayer})')
        self.assertEqual(self.page.evaluate('playedIds'), ['jfKfPfyJRdk'])
        self.page.evaluate("ytLoadDirect('dQw4w9WgXcQ')")
        self.assertEqual(self.page.evaluate('playedIds'), ['jfKfPfyJRdk', 'dQw4w9WgXcQ'])

    def test_tesla_without_integration_does_not_invent_vehicle_data(self):
        self.page.locator('.tesla-tab').click()
        expect(self.page.locator('#tesla-data-status')).to_have_text('● Sem integração Tesla')
        expect(self.page.locator('#hud-mode')).to_have_text('SEM DADOS')
        self.page.evaluate('''() => {
            window.tesla = {BatteryLevel: 80, ShiftState: 'D', VehicleSpeed: 90};
            refreshTeslaData();
        }''')
        expect(self.page.locator('#tesla-batt-pct')).to_have_text('--%')
        self.assertEqual(self.page.locator('.tdc-value.na').count(), 12)
        self.page.locator('#sim-btn').click()
        expect(self.page.locator('#hud-mode')).to_have_text('DEMO')
        self.page.locator('#sim-btn').click()
        expect(self.page.locator('#hud-mode')).to_have_text('SEM DADOS')

    def test_official_search_and_play(self):
        self.api_body = {'items': [{'id': {'videoId': 'dQw4w9WgXcQ'}, 'snippet': {'title': '<img src=x onerror=alert(1)>', 'channelTitle': 'Demo'}}]}
        self.page.locator('#yt-api-key').fill('test-api-key')
        self.page.locator('#yt-search-input').fill('music')
        self.page.locator('#yt-search-btn').click()
        expect(self.page.locator('.yt-result-title')).to_have_text('<img src=x onerror=alert(1)>')
        self.assertEqual(self.page.locator('.yt-result-title img').count(), 0)
        self.page.locator('.yt-result-item').click()
        expect(self.page.locator('#yt-open-video')).to_have_attribute('href', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self.assertIn('videoEmbeddable=true', self.requests[0].url)

    def test_api_failure_does_not_leave_search_disabled(self):
        self.api_status = 403
        self.page.locator('#yt-api-key').fill('test-api-key')
        self.page.locator('#yt-search-input').fill('music')
        self.page.locator('#yt-search-btn').click()
        expect(self.page.locator('#yt-results')).to_contain_text('quota')
        expect(self.page.locator('#yt-search-btn')).to_be_enabled()
        expect(self.page.locator('#yt-results a')).to_be_visible()

    def test_player_errors_offer_direct_link(self):
        self.page.evaluate("""() => {window.YT = {Player: function(id, options) {window.playerEvents = options.events;}}; onYouTubeIframeAPIReady(); playerEvents.onError({data:153});}""")
        expect(self.page.locator('#yt-message')).to_contain_text('identificação')
        self.page.evaluate('playerEvents.onError({data:150})')
        expect(self.page.locator('#yt-message')).to_contain_text('não permite')
        self.page.evaluate('playerEvents.onAutoplayBlocked()')
        expect(self.page.locator('#yt-message')).to_contain_text('Carrega em Play')

    def test_jellyfin_auth_and_library_with_base_path(self):
        self.login(SERVER + '/jellyfin/web/index.html#!/home.html')
        expect(self.page.locator('#jelly-lib-content')).to_contain_text('Test film')
        expect(self.page.locator('#jelly-badge')).to_have_text('LIGADO')
        auth = self.requests[0]
        self.assertEqual(auth.url, SERVER + '/jellyfin/Users/AuthenticateByName')
        self.assertEqual(auth.post_data_json, {'Username': 'demo', 'Pw': 'test-password'})
        self.assertNotIn('Token=', auth.headers['authorization'])
        self.assertIn('Token="test-token"', self.requests[1].headers['authorization'])
        expect(self.page.locator('#jelly-password')).to_have_value('')

    def test_auth_failure_is_specific_and_retry_has_no_old_token(self):
        self.auth_status = 401
        self.page.evaluate("jellyToken = 'stale-token'")
        self.login()
        expect(self.page.locator('#jellyfin-error')).to_contain_text('HTTP 401')
        self.assertNotIn('Token=', self.requests[0].headers['authorization'])
        self.auth_status = 200
        self.login()
        expect(self.page.locator('#jelly-badge')).to_have_text('LIGADO')
        expect(self.page.locator('#jellyfin-error')).not_to_be_visible()

    def test_mixed_content_is_explained_without_request(self):
        self.login('http://192.168.1.100:8096')
        expect(self.page.locator('#jellyfin-error')).to_contain_text('bloqueia HTTP')
        self.assertEqual(self.requests, [])

    def test_network_error_mentions_cors_not_bad_password(self):
        self.page.route(SERVER + '/**', lambda route: route.abort())
        self.login()
        expect(self.page.locator('#jellyfin-error')).to_contain_text('CORS')
        expect(self.page.locator('#jellyfin-error')).to_contain_text('https://andrenunesjob.github.io')

    def test_invalid_auth_response_cannot_show_connected(self):
        self.auth_body = {'User': {'Id': 'user-1'}}
        self.login()
        expect(self.page.locator('#jellyfin-error')).to_contain_text('Resposta de autenticação Jellyfin inválida')
        expect(self.page.locator('#jelly-badge')).to_have_text('DESLIGADO')

    def test_library_failure_is_not_a_password_error(self):
        self.views_status = 403
        self.login()
        expect(self.page.locator('#jellyfin-error')).to_contain_text('Autenticação aceite')
        expect(self.page.locator('#jellyfin-error')).to_contain_text('HTTP 403')
        expect(self.page.locator('#jellyfin-setup')).to_be_visible()
        expect(self.page.locator('#jelly-badge')).to_have_text('ERRO')


if __name__ == '__main__':
    unittest.main()
