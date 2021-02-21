from flask import g, jsonify, Flask, request, send_file, make_response
from flask_cors import CORS

from beets import ui
from beets.plugins import BeetsPlugin
from beets.library import Library
from PIL import Image
import base64
import io
import json

app = Flask(__name__)
app.config["DEBUG"] = True
CORS(app)


class BeetsAPI(BeetsPlugin):

    def __init__(self):
        super(BeetsAPI, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('api',
                            help=u'A nice api for Beets')
        cmd.func = self.command
        return [cmd]

    def command(self, lib, opt, args):
        app.config['lib'] = lib
        app.run(host='0.0.0.0', port=9999, debug=True)


@app.before_request
def before_request():
    g.lib = app.config['lib']


@app.route('/api/artist', methods=['GET'])
def get_all_artists():
    with g.lib.transaction() as tx:
        rows = tx.query("""
            SELECT albumartist, COUNT(albums.id) AS albumcount
            FROM albums
            GROUP BY albumartist
            ORDER BY albumartist COLLATE NOCASE
        """)
    all_artists = [serialize_row(row) for row in rows]
    return jsonify(artists=all_artists)


@app.route('/api/artist/<string:artist>/album', methods=['GET'])
def get_albums_of_artist(artist):
    artist = artist.replace("=+=", "/")
    with g.lib.transaction() as tx:
        rows = tx.query(f"""
            SELECT *
            FROM albums
            WHERE albumartist = '{artist}'
            ORDER BY original_year, original_month, original_day
        """)
    albums = [serialize_row(row) for row in rows]
    for a in albums:
        a['artdata'] = get_album_art_from_path(a['artpath'])

    # Get track count, duration
    with g.lib.transaction() as tx:
        rows = tx.query(f"""
            SELECT album, COUNT(id) AS tracktotal, SUM(length) AS duration
            FROM items
            WHERE albumartist = '{artist}'
            GROUP BY album
        """)
    albums_w_track_counts = {row['album']: serialize_row(row) for row in rows}
    for a in albums:
        a['tracktotal'] = albums_w_track_counts[a['album']]['tracktotal']
        a['duration'] = albums_w_track_counts[a['album']]['duration']

    return jsonify(albums=albums)


@app.route('/api/album', methods=['GET'])
def get_albums():
    with g.lib.transaction() as tx:
        rows = tx.query("""
            SELECT *
            FROM albums
            ORDER BY albumartist COLLATE NOCASE
        """)
    all_albums = {row[0]: serialize_row(row) for row in rows}
    return jsonify(albums=all_albums)


@app.route('/api/album/<int:album_id>/track')
def get_tracks_of_album(album_id):
    with g.lib.transaction() as tx:
        rows = tx.query(f"""
            SELECT *
            FROM items
            WHERE album_id = {album_id}
            ORDER BY track, disc
        """)
    all_items = [serialize_row(row) for row in rows]

    ## We still need to access each item via the regular API to access
    ## the flex attributes. Or figure out the sqlite table...
    ## See db.py for this code
    flex_attributes = ['rating', 'is_bonus', 'is_live', 'is_cover', 'is_instrumental', 'is_filler']
    for item in all_items:
        track = g.lib.get_item(item['id'])
        
        for flex in flex_attributes:
            if flex in track:
                item[flex] = track[flex]
        

    return jsonify(tracks=all_items)

@app.route('/api/album/<int:album_id>/art')
def get_album_art(album_id):
    with g.lib.transaction() as tx:
        rows = tx.query(f"""
            SELECT artpath
            FROM albums
            WHERE id = {album_id}
        """)
    with open(str(rows[0]['artpath'], 'utf-8'), "rb") as f:
        img_binary = f.read()
        im = Image.open(f)
        size = 128, 128
        im.thumbnail(size)
        im = im.convert('RGB')
        
        b = io.BytesIO()
        im.save(b, 'jpeg')
        img = base64.b64encode(b.getvalue()).decode("utf-8")
        return jsonify({'image': img})
    return None

@app.route('/api/album_type')
def get_album_types():
    with g.lib.transaction() as tx:
        rows = tx.query(f"""
            SELECT albumtype, COUNT(id) AS cnt
            FROM albums
            GROUP BY albumtype
            ORDER BY cnt DESC
        """)
    all_types = [row['albumtype'] for row in rows]
    return jsonify(albumtypes=all_types)

@app.route('/api/track/<int:track_id>/rate', methods=['PUT'])
def rate_track(track_id):
    rating = json.loads(request.data)['rating']
    track = g.lib.get_item(track_id)
    track['rating'] = rating
    try:
        track.write()
        track.store()
    except (ReadError, WriteError) as e:
        print(e)

    return jsonify(wowee={'foo': 3})

@app.route('/api/track/<int:track_id>/tag', methods=['PUT'])
def tag_track(track_id):
    payload = json.loads(request.data)
    tag_to_set = payload['tag']
    new_value = payload['newValue']
    track = g.lib.get_item(track_id)

    track[tag_to_set] = new_value
    try:
        track.write()
        track.store()
    except (ReadError, WriteError) as e:
        print(e)

    return jsonify(wowee={'foo': 3})

def get_album_art_from_path(path):
    with open(path, "rb") as f:
        img_binary = f.read()
        im = Image.open(f)
        size = 128, 128
        im.thumbnail(size)
        im = im.convert('RGB')
        
        b = io.BytesIO()
        im.save(b, 'jpeg')
        img = base64.b64encode(b.getvalue()).decode("utf-8")
        return img


def serialize_row(row):
    omit = []
    asObj = {key: row[key] for key in row.keys() if key not in omit}
    if 'artpath' in asObj:
        asObj['artpath'] = str(asObj['artpath'], 'utf-8')
    if 'path' in asObj:
        asObj['path'] = str(asObj['path'], 'utf-8')
    return asObj
