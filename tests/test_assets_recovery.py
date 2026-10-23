"""Public resources must render completely without bundling private server data."""
import importlib.util
import json
from pathlib import Path
import zipfile

from PIL import Image
from fontTools.ttLib import TTFont
from unsent.shared.catalog import asset_reference, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_every_fictional_profile_has_a_complete_bilingual_photo_grid():
    catalog = load_catalog(ROOT / 'assets')
    assert set(catalog.characters) == {'rio', 'jiwoo', 'yuna'}
    assert len(catalog.posts) == 18
    for character in catalog.characters.values():
        assert len(character.post_ids) == 6
        assert all(character.translations['en'][key] for key in ('display_name', 'bio', 'note', 'greeting'))
    assert len(catalog.posts['rio_0'].images) >= 2
    references = [catalog.self_avatar] + [c.avatar for c in catalog.characters.values()]
    for post in catalog.posts.values():
        references.extend(post.images)
        assert post.translations['en']['caption'] and post.translations['en']['description']
    for reference in references:
        filename, crop = asset_reference(reference)
        with Image.open(ROOT / 'assets' / filename) as image:
            assert crop is not None
            x, y, width, height = crop
            assert x + width <= image.width and y + height <= image.height
            assert width >= 200 and height >= 200


def test_both_font_weights_cover_korean_and_english_without_system_fonts():
    for weight in ('Regular', 'Bold'):
        font = TTFont(ROOT / 'assets' / 'fonts' / f'NotoSansKR-{weight}.ttf')
        table = font.getBestCmap()
        assert all(ord(char) in table for char in '안녕하세요읽음메시지English')


def test_browser_package_uses_an_allowlist_and_never_packages_backend(tmp_path):
    spec = importlib.util.spec_from_file_location('web_builder', ROOT / 'tools' / 'build_web.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    project = tmp_path / 'project'
    for filename, value in {
        'src/unsent/__init__.py': '',
        'src/unsent/client/main.py': 'print("public")',
        'src/unsent/shared/contracts.py': '',
        'src/unsent/domain/state.py': '',
        'assets/public.json': '{}',
        'src/unsent/backend/secrets.py': 'PRIVATE',
        '.env': 'PRIVATE',
        '.local/browser-data.json': 'PRIVATE',
        'src/unsent/client/__pycache__/main.pyc': 'PRIVATE',
        'assets/.private-settings': 'PRIVATE',
    }.items():
        target = project / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
    target = builder.package_client(project, tmp_path / 'app.zip')
    with zipfile.ZipFile(target) as package:
        names = set(package.namelist())
        assert 'unsent/client/main.py' in names and 'assets/public.json' in names
        assert not any('PRIVATE' in package.read(name).decode() for name in names)
        assert not any('backend' in name or '__pycache__' in name or name.startswith('.') for name in names)


def test_local_launcher_profiles_cannot_share_identity_keys_or_escape_names(tmp_path):
    from tools.launch_local import create_web_app, profile_directory, validate_bind
    first = profile_directory('first', project=tmp_path)
    second = profile_directory('second', project=tmp_path)
    assert first != second and first.stat().st_mode & 0o777 == 0o700
    for name in ('../other', '/tmp/public', '', 'a.b'):
        try:
            profile_directory(name, project=tmp_path)
        except ValueError:
            pass
        else:
            raise AssertionError('Unsafe profile accepted')
    for host in ('0.0.0.0', '192.168.1.10', 'example.com'):
        try:
            validate_bind(host, None)
        except ValueError:
            pass
        else:
            raise AssertionError('Public bind accepted without explicit access token')
    # Reusing the configured default model is an explicit default-profile choice.
    # A second named profile must be unconfigured until it opts into a model.
    local = tmp_path / '.local'
    (local / 'config.toml').write_text('[model]\nprovider="ollama"\nbase_url="http://127.0.0.1:11434"\nname="private-model"\n')
    app = create_web_app(project=tmp_path, profile='second', build_client=False)
    assert app.state.settings.provider is None
    assert app.state.settings.data_dir == str(second)
    assert (second / 'identity.key').stat().st_mode & 0o777 == 0o600


def test_enabled_browser_runtime_features_have_pinned_local_dependencies():
    from html.parser import HTMLParser
    from tools.build_web import RUNTIME_HASHES
    class ScriptFeatures(HTMLParser):
        enabled = set()
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == 'script' and values.get('src') == '/runtime/pythons.js':
                self.enabled.update(values.get('data-os', '').split(','))
    parser = ScriptFeatures()
    parser.feed((ROOT / 'web/template.tmpl').read_text())
    dependencies = {'fs': ('browserfs.min.js',), 'snd': ('empty.ogg',), 'vtx': ('vtx.js',)}
    for feature in parser.enabled:
        for filename in dependencies.get(feature, ()):
            assert filename in RUNTIME_HASHES, f'{feature} needs a local pinned {filename}'


async def test_same_origin_repository_adapter_is_safe_when_runtime_reloads_indexes(monkeypatch):
    import sys
    import types
    from tools.build_web import SAME_ORIGIN_ADAPTER
    config = types.SimpleNamespace(PKG_INDEXES=['https://old.invalid/'], dev_mode=0,
        pkg_repolist=[{'-CDN-': 'https://old.invalid/'}])
    async def upstream_async_repos():
        fresh = {'-CDN-': 'https://pygame-web.github.io/archives/repo/'}
        if fresh not in config.pkg_repolist:
            config.pkg_repolist.append(fresh)
        if config.dev_mode:
            for index, repository in enumerate(config.pkg_repolist):
                repository['-CDN-'] = config.PKG_INDEXES[index]
    pep = types.ModuleType('aio.pep0723')
    pep.Config = config
    pep.async_repos = upstream_async_repos
    aio = types.ModuleType('aio')
    aio.pep0723 = pep
    monkeypatch.setitem(sys.modules, 'aio', aio)
    monkeypatch.setitem(sys.modules, 'aio.pep0723', pep)
    namespace = {'platform': types.SimpleNamespace(window=types.SimpleNamespace(location=types.SimpleNamespace(origin='http://127.0.0.1:8765')))}
    exec(SAME_ORIGIN_ADAPTER, namespace)
    await pep.async_repos()
    await pep.async_repos()
    assert config.PKG_INDEXES == ['http://127.0.0.1:8765/runtime/repo/']
    assert config.pkg_repolist == [{'-CDN-': config.PKG_INDEXES[0]}]
