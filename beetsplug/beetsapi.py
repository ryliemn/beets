from flask import g, jsonify, Flask, request

from beets import ui
from beets.plugins import BeetsPlugin
from beets.library import Library

app = Flask(__name__)
app.config["DEBUG"] = True


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
        app.run(host='0.0.0.0', port=9999)


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
        """)
    all_artists = [serialize_row(row) for row in rows]
    return jsonify(artists=all_artists)


@app.route('/api/artist/<string:artist>/album', methods=['GET'])
def get_albums_of_artist(artist):
    with g.lib.transaction() as tx:
        rows = tx.query(f"""
            SELECT *
            FROM albums
            WHERE albumartist = '{artist}'
        """)
    albums = {row['id']: serialize_row(row) for row in rows}
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
    all_items = {row['id']: serialize_row(row) for row in rows}
    return jsonify(items=all_items)


def serialize_row(row):
    omit = ['artpath', 'path']
    return {key: row[key] for key in row.keys() if key not in omit}
