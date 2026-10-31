"""Browser regression checks. Run: python3 -m unittest discover -s tests -v"""
import json
from pathlib import Path
import unittest
from urllib.parse import urlparse, parse_qs
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
        self.library_views = [{'Id': 'movies', 'Name': 'Filmes', 'CollectionType': 'movies'}]
        self.episodes = [
            {'Id': 'ep-10', 'Name': 'Finale', 'Type': 'Episode', 'IndexNumber': 10},
            {'Id': 'ep-2', 'Name': 'Second episode', 'Type': 'Episode', 'IndexNumber': 2},
        ]
        self.episodes_status = 200
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.route('**/*', self.route)
        self.page.goto(SITE, wait_until='domcontentloaded')
        self.page.locator('summary').click()
        self.initial_search_server = self.page.locator('#yt-search-server').input_value()
        self.page.locator('#yt-search-server').fill('')

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
                route.fulfill(status=self.views_status, content_type='application/json', body=json.dumps({'Items': self.library_views}))
            elif urlparse(request.url).path.endswith('/Shows/show-1/Seasons'):
                route.fulfill(content_type='application/json', body=json.dumps({'Items': [
                    {'Id': 'season-10', 'Name': 'Season 10', 'Type': 'Season', 'IndexNumber': 10},
                    {'Id': 'specials', 'Name': 'Specials', 'Type': 'Season', 'IndexNumber': 0},
                    {'Id': 'season-2', 'Name': 'Season 2', 'Type': 'Season', 'IndexNumber': 2},
                ]}))
            elif urlparse(request.url).path.endswith('/Shows/show-1/Episodes'):
                route.fulfill(status=self.episodes_status, content_type='application/json', body=json.dumps({'Items': self.episodes}))
            elif '/PlaybackInfo?' in request.url:
                route.fulfill(content_type='application/json', body=json.dumps({'MediaSources': [{'Id': 'source-1'}]}))
            elif parse_qs(urlparse(request.url).query).get('ParentId') == ['tv']:
                route.fulfill(content_type='application/json', body=json.dumps({'Items': [{'Id': 'show-1', 'Name': 'Test show', 'Type': 'Series'}]}))
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

    def test_keyless_server_search_plays_results_and_remembers_address(self):
        self.assertEqual(self.initial_search_server, 'https://mobile.oqen.pt')
        captured = []
        def respond(route):
            captured.append(route.request.url)
            route.fulfill(content_type='application/json', body=json.dumps({'items': [
                {'id': 'dQw4w9WgXcQ', 'title': 'Keyless result', 'channel': 'Demo'},
                {'id': 'not-a-video-id', 'title': 'Invalid result'},
            ]}))
        self.page.route('https://mobile.oqen.pt/api/search?*', respond)
        self.page.locator('#yt-search-server').fill('https://mobile.oqen.pt/')
        expect(self.page.locator('#yt-search-btn')).to_have_text('🔍 Pesquisar aqui')
        self.page.locator('#yt-search-input').fill('lofi & music')
        self.page.locator('#yt-search-btn').click()
        expect(self.page.locator('.yt-result-title')).to_have_text('Keyless result')
        self.assertEqual(parse_qs(urlparse(captured[0]).query), {'q': ['lofi & music']})
        self.assertEqual(self.requests, [])  # No Google API key or request involved.
        self.page.locator('.yt-result-item').click()
        expect(self.page.locator('#yt-open-video')).to_have_attribute('href', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self.page.reload(wait_until='domcontentloaded')
        expect(self.page.locator('#yt-search-server')).to_have_value('https://mobile.oqen.pt/')

    def test_keyless_server_failure_has_actionable_error_and_fallback(self):
        self.page.route('https://mobile.oqen.pt/api/search?*', lambda route: route.fulfill(
            status=502, content_type='application/json', body=json.dumps({'error': 'YouTube bloqueou a pesquisa da VPS.'})))
        self.page.locator('#yt-search-server').fill('https://mobile.oqen.pt')
        self.page.locator('#yt-search-input').fill('music')
        self.page.locator('#yt-search-btn').click()
        expect(self.page.locator('#yt-results')).to_contain_text('YouTube bloqueou a pesquisa da VPS.')
        expect(self.page.locator('#yt-results a')).to_be_visible()
        expect(self.page.locator('#yt-search-btn')).to_be_enabled()

    def test_keyless_server_rejects_http_before_sending_request(self):
        self.page.locator('#yt-search-server').fill('http://mobile.oqen.pt')
        self.page.locator('#yt-search-input').fill('music')
        self.page.locator('#yt-search-btn').click()
        expect(self.page.locator('#yt-results')).to_contain_text('URL HTTPS')
        expect(self.page.locator('#yt-search-btn')).to_be_enabled()

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

    def open_tv_season(self):
        self.library_views.append({'Id': 'tv', 'Name': 'TV', 'CollectionType': 'tvshows'})
        self.login()
        self.page.locator('.jelly-section-btn', has_text='TV').click()
        expect(self.page.locator('.jelly-media-title')).to_have_text('Test show')
        self.page.locator('.jelly-media-item').click()
        expect(self.page.locator('.jelly-media-title')).to_have_text(['Specials', 'Season 2', 'Season 10'])
        self.page.locator('.jelly-media-item', has_text='Season 2').click()

    def test_tv_groups_series_seasons_episodes_and_preserves_return_location(self):
        self.open_tv_season()
        expect(self.page.locator('.jelly-media-title')).to_have_text(['2. Second episode', '10. Finale'])
        tv_request = next(r for r in self.requests if 'ParentId=tv' in r.url)
        self.assertEqual(parse_qs(urlparse(tv_request.url).query)['IncludeItemTypes'], ['Series'])
        episode_request = next(r for r in self.requests if '/Episodes?' in r.url)
        self.assertEqual(parse_qs(urlparse(episode_request.url).query)['SeasonId'], ['season-2'])
        self.assertFalse(any('/PlaybackInfo?' in r.url for r in self.requests))
        self.page.locator('.jelly-media-item', has_text='Second episode').click()
        expect(self.page.locator('#jellyfin-player-wrap')).to_be_visible()
        expect(self.page.locator('#jellyfin-video')).to_have_attribute('src', SERVER + '/Videos/ep-2/stream?Static=true&MediaSourceId=source-1&api_key=test-token')
        self.page.locator('#jellyfin-player-wrap button').click()
        expect(self.page.locator('.jelly-media-title')).to_have_text(['2. Second episode', '10. Finale'])
        expect(self.page.locator('#jelly-breadcrumbs button[aria-current="page"]')).to_have_text('Season 2')
        self.page.evaluate('jellyRefresh()')
        expect(self.page.locator('.jelly-media-title')).to_have_text(['2. Second episode', '10. Finale'])
        self.assertIn('/Episodes?', self.requests[-1].url)
        self.page.locator('#jelly-breadcrumbs button', has_text='Test show').click()
        expect(self.page.locator('.jelly-media-title')).to_have_text(['Specials', 'Season 2', 'Season 10'])
        self.page.locator('#jelly-breadcrumbs button', has_text='TV').click()
        expect(self.page.locator('.jelly-media-title')).to_have_text('Test show')

    def test_movies_still_open_player_directly(self):
        self.login()
        expect(self.page.locator('.jelly-media-title')).to_have_text('Test film')
        self.page.locator('.jelly-media-item').click()
        expect(self.page.locator('#jellyfin-player-wrap')).to_be_visible()
        expect(self.page.locator('#jelly-np-title')).to_have_text('Test film')
        self.assertFalse(any('/Seasons?' in r.url or '/Episodes?' in r.url for r in self.requests))

    def test_empty_season_and_failed_request_can_be_retried(self):
        self.episodes = []
        self.open_tv_season()
        expect(self.page.locator('#jelly-lib-content')).to_have_text('Nenhum episódio disponível.')
        self.episodes_status = 500
        self.page.evaluate('jellyRefresh()')
        expect(self.page.locator('#jelly-lib-content')).to_contain_text('HTTP 500')
        self.episodes_status = 200
        self.episodes = [{'Id': 'ep-1', 'Name': 'Pilot', 'Type': 'Episode', 'IndexNumber': 1}]
        self.page.evaluate('jellyRefresh()')
        expect(self.page.locator('.jelly-media-title')).to_have_text('1. Pilot')
        self.page.locator('.jelly-section-btn', has_text='Filmes').click()
        expect(self.page.locator('#jelly-breadcrumbs button')).to_have_text('Filmes')
        expect(self.page.locator('.jelly-media-title')).to_have_text('Test film')

    def test_late_seasons_response_does_not_replace_another_library(self):
        self.library_views.append({'Id': 'tv', 'Name': 'TV', 'CollectionType': 'tvshows'})
        self.login()
        held = []
        self.page.route('**/Shows/show-1/Seasons?*', lambda route: held.append(route))
        self.page.locator('.jelly-section-btn', has_text='TV').click()
        self.page.locator('.jelly-media-item', has_text='Test show').click()
        expect(self.page.locator('#jelly-lib-content')).to_have_text('A carregar...')
        self.page.locator('.jelly-section-btn', has_text='Filmes').click()
        expect(self.page.locator('.jelly-media-title')).to_have_text('Test film')
        self.assertEqual(len(held), 1)
        held[0].fulfill(content_type='application/json', body=json.dumps({'Items': [{'Id': 'late', 'Name': 'Late season', 'Type': 'Season'}]}))
        self.page.evaluate('new Promise(requestAnimationFrame)')
        expect(self.page.locator('.jelly-media-title')).to_have_text('Test film')
        expect(self.page.locator('#jelly-breadcrumbs button')).to_have_text('Filmes')


if __name__ == '__main__':
    unittest.main()
