#!/usr/bin/env python3
import re
import shlex
import subprocess
import click
from plexapi.exceptions import BadRequest, NotFound
from plexapi.myplex import MyPlexAccount
import keyring
from keyring.errors import PasswordDeleteError
from urllib.parse import unquote
import pyperclip
import json
from datetime import datetime

# UTILS

# Ask User for Credentials


def ask_for_credentials():
    username = click.prompt('Enter Plex username')
    password = click.prompt('Enter Plex password',
                            hide_input=True)
    # Ask user if 2FA is enabled, if so ask for pin
    two_factor = click.confirm('Is 2FA enabled?')
    if two_factor:
        pin = click.prompt('Enter 2FA code')
    else:
        pin = None
    return username, password, pin

# Copy Link to Clipboard


def copy_to_clipboard(url):
    try:
        pyperclip.copy(url)
    except AttributeError:
        raise click.ClickException(
            'Clipboard not available, please copy the link manually')
    except Exception:
        raise click.ClickException(
            'Could not copy link to clipboard, please copy the link manually')


# Save User Credentials


def save_credentials(token):
    try:
        with open('userdata/settings.json', 'r') as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}
    
    settings['plex_token'] = token

    with open('userdata/settings.json', 'w') as f:
        json.dump(settings, f, indent=2)

# Get User Credentials


def get_credentials():
    try:
        with open('userdata/settings.json', 'r') as f:
            settings = json.load(f)
        token = settings.get('plex_token')
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        token = None
    if token:        
        return token
    else:
        return "no_token"
        
# list of servers


def list_servers(account):
    return [{'name': server.name, 'id': server.clientIdentifier}
            for server in account.resources()]

# Get Plex Account


def get_account():
    # Get credentials
    credentials = get_credentials()
    # If credentials exist
    if credentials != "no_token":
        # Get account
        try:
            account = MyPlexAccount(token=credentials)
            return account
        except Exception as e:
            raise BadRequest('Error connecting to Plex account: {}'.format(e))
    else:
        raise click.ClickException(
            'No credentials found, please authenticate first')


def write_m3u8_file(playlist_title, items):
    with open(f"{playlist_title}.m3u8", "w") as f:
        f.write("#EXTM3U\n")
        for item in items:
            f.write(f"#EXTINF:{(item[2] / 1000)}, {item[1]}\n{item[0]}\n")

# PLAYLISTS


def list_playlists(account, server_name):
    try:
        plex = account.resource(server_name).connect()
        return plex.playlists()
    except Exception as e:
        raise click.ClickException(str(e))


def get_playlist_info(account, server_name, playlist_title):
    plex = account.resource(server_name).connect()
    playlist = plex.playlist(playlist_title)

    item_info = []
    for item in playlist.items():
        base_url = item._server._baseurl
        media_url = item.media[0].parts[0].key
        token = item._server._token
        url = f"{base_url}{media_url}?X-Plex-Token={token}&download=1;{item.duration}"
        duration = item.duration
        file_name = item.media[0].parts[0].file.split("/")[-1]
        item_info.append((url, file_name, duration))
    return item_info

def get_epg_data_for_playlist(account, server_name, playlist_title):
    """
    Returns a list of dicts with EPG-like metadata for each movie in the playlist,
    including the full media URL with Plex token.
    """
    plex = account.resource(server_name).connect()
    playlist = plex.playlist(playlist_title)
    epg_data = []
    for item in playlist.items():
        base_url = item._server._baseurl
        token = item._server._token
        media_url = item.media[0].parts[0].key if item.media and item.media[0].parts else ""
        full_url = f"{base_url}{media_url}?X-Plex-Token={token}&download=1" if media_url else ""
        # Staffel (season) und Folge (episode) extrahieren, falls vorhanden
        season = getattr(item, "parentIndex", None)
        episode = getattr(item, "index", None)
        series_title = getattr(item, "grandparentTitle", "")  # Serienname
        data = {
            "title": getattr(item, "title", ""),
            "year": getattr(item, "year", ""),
            "summary": getattr(item, "summary", ""),
            "duration": getattr(item, "duration", 0),
            "rating": getattr(item, "rating", ""),
            "content_rating": getattr(item, "contentRating", ""),
            "genres": [g.tag for g in getattr(item, "genres", [])],
            "directors": [d.tag for d in getattr(item, "directors", [])],
            "writers": [w.tag for w in getattr(item, "writers", [])],
            "actors": [a.tag for a in getattr(item, "actors", [])],
            "thumb": base_url + getattr(item, "thumb", "") + f"?X-Plex-Token={token}",
            "art": base_url + getattr(item, "art", "") + f"?X-Plex-Token={token}",
            "original_title": getattr(item, "originalTitle", ""),
            "studio": getattr(item, "studio", ""),
            "guid": getattr(item, "guid", ""),
            "addedAt": getattr(item, "addedAt", ""),
            "updatedAt": getattr(item, "updatedAt", ""),
            "url": full_url,
            "season": season,
            "episode": episode,
            "series_title": series_title  # Serienname hinzufügen
            
        }
        epg_data.append(data)
    return epg_data


def get_download_url(web_url):
    if not web_url:
        raise click.ClickException('No URL provided')

    # unquote url
    web_url = unquote(web_url)

    # Regex
    pattern_server_id = r"(?<=server\/)[^\/]+"
    pattern_metadata_key = r"(?<=metadata\/)\d+"

    server_id = re.search(pattern_server_id, web_url)
    metadata_key = re.search(pattern_metadata_key,
                             web_url)

    if not server_id or not metadata_key:
        raise click.ClickException("Invalid URL")

    server_id = server_id.group(0)
    metadata_key = metadata_key.group(0).replace("\\", "")

    # if metadata_key or server_id is empty, raise exception
    if not server_id or not metadata_key:
        raise click.ClickException("Invalid URL")

    # Get account
    account = get_account()

    # Get servers
    servers = list_servers(account)

    # find the server using a generator expression and the `next` function
    server = next(
        (server for server in servers if server['id'] == server_id), None)
    if not server:
        raise BadRequest('Server not found')

    # get media and construct the download URL
    plex = account.resource(server['name']).connect()
    try:
        media = plex.fetchItem(int(metadata_key))
    except NotFound:
        raise click.ClickException('Media not found')

    base_url = media._server._baseurl
    media_url = media.media[0].parts[0].key
    token = media._server._token
    url = f"{base_url}{media_url}?X-Plex-Token={token}"

    return url


@click.group()
def plex():
    pass


@click.command(name='auth')
@click.option('--username', prompt=False, help='Plex username')
@click.option('--password', prompt=False, hide_input=True, help='Plex password')
@click.option('--pin', prompt=False, help='2FA code')
def authenticate_cli(username, password, pin):
    try:
        if get_credentials() != "no_token":
            click.echo('Already authenticated')
            return
        # Prompt for credentials if not provided
        if not all([username, password]):
            username, password, pin = ask_for_credentials()

        # Authenticate user
        account = MyPlexAccount(username, password, code=pin)
        # Get token
        token = account.authenticationToken
        # Save token
        save_credentials(token)
        click.echo('Authentication successful')
    except Exception as e:
        click.echo('Error: {}'.format(e))


@click.command(name='download')
@click.argument('query')
def download_media_cli(query):
    try:
        url = get_download_url(query)
        click.echo(url)
        copy_to_clipboard(url)
    except Exception as e:
        click.echo('Error: {}'.format(e))

@click.command(name='signout')
def signout_cli():
    try:
        try:
            with open('userdata/settings.json', 'r') as f:
                settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            settings = {}

        settings['plex_token'] = "no_token"

        with open('userdata/settings.json', 'w') as f:
            json.dump(settings, f, indent=2)
            
        click.echo('Signed out successfully')
    except:
        click.echo('No credentials found')


@click.command(name='playlist')
@click.option('--m3u', is_flag=True, help='Save as m3u playlist')
def playlist_cli(m3u):
    from pathlib import Path
    account = get_account()

    # List servers
    servers = list_servers(account)

    click.echo("Choose a server:")
    for index, server in enumerate(servers, start=1):
        click.echo(f"{index}. {server['name']}")


        # Get server_index from settings if available
        try:
            with open('userdata/settings.json', 'r') as f:
                settings = json.load(f)
            server_index_json = settings.get('server_index', "ask")
        except (FileNotFoundError, json.JSONDecodeError):
            server_index_json = "ask"


    if server_index_json == "ask":
        server_index = click.prompt(
            "Enter server number", type=int) - 1
    elif server_index_json.isdigit():
        server_index = int(server_index_json) - 1

    try:
        server_name = servers[server_index]['name']
    except IndexError:
        raise click.ClickException('Invalid server number')

    click.echo("Playlist files getting generated now:")
    playlists = list_playlists(account, server_name)

    # If no playlists, exit
    if not playlists:
        click.echo("No playlists found")
        return

    try:
        playlist_index = 0
        for playindex in playlists:
            playlist_title = playlists[playlist_index].title

            media_info = get_playlist_info(account, server_name, playlist_title)
            epg_data = get_epg_data_for_playlist(account, server_name, playlist_title)
            script_dir = Path(__file__).parent
            path = script_dir / "userdata" / "movies" / playlist_title
            path.mkdir(parents=True, exist_ok=True)

            file = open(path / "playlist.txt", "w")
            file.write("")
            file.close()

            for item in media_info:
                file = open(path / "playlist.txt", "a")
                file.write(f"{item[0]} \n")
                file.close()
            print(playlist_title + " written to " + str(path) + "/playlist.txt")
            


            def default_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)

            with open(path / "epg.json", "w") as file:
                for item in epg_data:
                    file.write(json.dumps(item, default=default_serializer) + "\n")
            print(playlist_title + " written to " + str(path) + "/epg.json")

            subprocess.run(shlex.split(f'{script_dir}/videopipe.py --moviename {playlist_title} --epg --epgupdate'))
            
            playlist_index = playlist_index + 1
            
            
    except IndexError:
        click.echo("Invalid playlist number" + str(playlist_index))
        return




plex.add_command(authenticate_cli)
plex.add_command(download_media_cli)
plex.add_command(signout_cli)
plex.add_command(playlist_cli)


if __name__ == '__main__':
    plex()
