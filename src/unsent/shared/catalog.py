import json
from pathlib import Path
from unsent.shared.contracts import Catalog, Character, Post


def asset_reference(value):
    """Split a public asset filename and optional atlas source rectangle."""
    filename, marker, fragment = value.partition('#')
    if not marker:
        return filename, None
    try:
        region = tuple(int(part) for part in fragment.split(','))
    except ValueError as exc:
        raise ValueError('Invalid atlas reference') from exc
    if len(region) != 4 or min(region[:2]) < 0 or min(region[2:]) <= 0:
        raise ValueError('Invalid atlas reference')
    return filename, region


def load_catalog(asset_root):
    root = Path(asset_root).resolve()
    data = json.loads((root / 'characters.json').read_text())
    def check_asset(value):
        filename, _ = asset_reference(value)
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Invalid or missing asset path')
    check_asset(data['self_avatar'])
    characters = {item['id']:Character(**item) for item in data['characters']}
    posts = {item['id']:Post(**item) for item in data['posts']}
    for character in characters.values():
        check_asset(character.avatar)
        if any(pid not in posts or posts[pid].character_id != character.id for pid in character.post_ids):
            raise ValueError('Invalid profile post reference')
    for post in posts.values():
        if not post.images:
            raise ValueError('Post needs an image')
        for image in post.images:
            check_asset(image)
    return Catalog(characters, posts, data['self_avatar'])
