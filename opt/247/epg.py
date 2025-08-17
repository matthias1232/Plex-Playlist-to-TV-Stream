#!/usr/bin/env python3
import argparse
import os
import json
import datetime
import xml.etree.ElementTree as ET

# Argumente
parser = argparse.ArgumentParser(description="EPG aus JSON-Metadaten erzeugen")
parser.add_argument("--epgfile", required=True, help="Pfad zur .epg.json-Datei (mit JSON-Inhalt)")
parser.add_argument("--offset", type=int, default=0, help="Startversatz in Sekunden")
parser.add_argument("--startline", type=int, default=1, help="Startindex (1-basiert)")
parser.add_argument("--output", type=str, default="epg.xml", help="Pfad zur Ausgabedatei (XML)")
args = parser.parse_args()


# Inhalte laden
with open(args.epgfile, "r", encoding="utf-8") as f:
    raw_data = f.read()

# Channel = Ordnername
channel_name = os.path.basename(os.path.dirname(os.path.abspath(args.epgfile)))
channel_name = f"{channel_name}"
# Startzeit
start_time = datetime.datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
start_time += datetime.timedelta(seconds=args.offset)

# EPG-Struktur vorbereiten
tv = ET.Element("tv")

# Channel-Element wie bei TV-EPG
channel = ET.SubElement(tv, "channel", id=channel_name)
ET.SubElement(channel, "display-name", lang="de").text = channel_name

# Optional: Logo/Bild falls in JSON vorhanden oder Standardbild
logo_url = None
# Versuche, das erste Bild aus der EPG-Datei zu nehmen
try:
    items_preview = json.loads(raw_data)
    if isinstance(items_preview, dict):
        items_preview = [items_preview]
    for item in items_preview:
        if "image" in item and item["image"]:
            logo_url = item["image"]
            break
except Exception:
    pass

if not logo_url:
    # Fallback: Standardbild oder leer lassen
    logo_url = ""

ET.SubElement(channel, "icon", src=logo_url)
tv = ET.Element("tv")
max_duration = 365 * 24 * 60 * 60
elapsed = 0



# JSON-Objekte parsen (ein JSON pro Zeile oder Block)
try:
    # Versuche, das gesamte File als JSON-Array zu laden
    items = json.loads(raw_data)
    if isinstance(items, dict):
        items = [items]
except json.JSONDecodeError:
    # Fallback: Zeilenweise laden (JSON pro Zeile)
    items = []
    for line in raw_data.splitlines():
        line = line.strip()
        if line:
            try:
                item = json.loads(line)
                items.append(item)
            except json.JSONDecodeError:
                continue

# Startzeit auf jetzt setzen
start_time = datetime.datetime.now().replace(microsecond=0)
items = [item for item in items if "title" in item]

# Optional ab Zeile X starten
index = max(0, args.startline - 1)

while elapsed < max_duration:
    item = items[index % len(items)]
    # Staffel und Folge ergänzen, falls vorhanden
    season = item.get("season")
    episode = item.get("episode")
    series_title = item.get("series_title")
    title = item.get("title", f"Folge {index + 1}")
    #print(season, episode)
    if season is not None and episode is not None and series_title is not None:
        title = f"{series_title} - {title} (S{season:02d}E{episode:02d})"
    elif season is not None and series_title is not None:
        title = f"{series_title} - {title} (S{season:02d})"
    elif episode is not None and series_title is not None:
        title = f"{series_title} - {title} (E{episode:02d})"
        
    desc = item.get("summary", "")
    year = item.get("year")
    duration_ms = item.get("duration", 0)
    duration = duration_ms // 1000
    end_time = start_time + datetime.timedelta(seconds=duration)

    # Kodi-Beschreibung zusammenbauen
    desc_parts = []
    if year:
        desc_parts.append(str(year))
    if season is not None and episode is not None:
        desc_parts.append(f"S{int(season)} E{int(episode)}")
    elif season is not None:
        desc_parts.append(f"S{int(season)}")
    elif episode is not None:
        desc_parts.append(f"E{int(episode)}")
    if item.get("content_rating"):
        desc_parts.append(f"FSK: {item['content_rating']}")
    # Verwende den Unicode Bullet (●) als Trenner
    kodi_desc = " ● ".join(desc_parts)
    if kodi_desc:
        kodi_desc += "\n"
    kodi_desc += desc  # eigentliche Beschreibung in neuer Zeile anhängen

    # Basis-EPG-Eintrag
    local_offset = datetime.datetime.now().astimezone().strftime("%z")
    programme = ET.SubElement(tv, "programme", {
        "start": start_time.strftime("%Y%m%d%H%M%S") + " " + local_offset,
        "stop": end_time.strftime("%Y%m%d%H%M%S") + " " + local_offset,
        "channel": channel_name
    })
    ET.SubElement(programme, "title", lang="de").text = f"{title}"
    ET.SubElement(programme, "desc", lang="de").text = kodi_desc

    # Jahr als eigenes Feld
    if year:
        ET.SubElement(programme, "date").text = str(year)
        
    # Erweiterte Felder
    if item.get("content_rating"):
        ET.SubElement(programme, "rating", system="FSK").text = item["content_rating"]
    if item.get("directors"):
        for director in item["directors"]:
            ET.SubElement(programme, "director").text = director
    if item.get("writers"):
        for writer in item["writers"]:
            ET.SubElement(programme, "writer").text = writer
    if item.get("actors"):
        for actor in item["actors"]:
            ET.SubElement(programme, "actor").text = actor

    # Originaltitel (falls vorhanden)
    if item.get("original_title"):
        ET.SubElement(programme, "sub-title", lang="de").text = item["original_title"]

    # Erscheinungsdatum / Hinzugefügt
    if item.get("addedAt"):
        try:
            dt = datetime.datetime.fromisoformat(item["addedAt"])
            ET.SubElement(programme, "date").text = dt.strftime("%Y-%m-%d")
        except:
            pass

    # Studio
    if item.get("studio"):
        ET.SubElement(programme, "producer").text = item["studio"]

    # GUID als episode-num
    if item.get("guid"):
        ET.SubElement(programme, "episode-num", system="plex").text = item["guid"]

    # URL zur Datei
    if item.get("url"):
        ET.SubElement(programme, "url").text = item["url"]

    # Poster / Thumbnail
    if item.get("thumb"):
        ET.SubElement(programme, "icon", src=item["thumb"])

    # Hintergrundbild / Artwork
    if item.get("art"):
        ET.SubElement(programme, "icon", attrib={"src": item["art"], "type": "background"})
        # Download and save artwork as logo.png (only once)
        if item.get("art") and not hasattr(args, '_logo_downloaded'):
            try:
                import urllib.request
                output_dir = os.path.dirname(os.path.abspath(args.output))
                logo_path = os.path.join(output_dir, "logo.png")
                urllib.request.urlretrieve(item["art"], logo_path)
                args._logo_downloaded = True  # Mark as downloaded
            except Exception as e:
                print(f"⚠️ Failed to download artwork: {e}")


    # Zeiten aktualisieren
    start_time = end_time
    elapsed += duration
    index += 1

# XML ausgeben
tree = ET.ElementTree(tv)
ET.indent(tree, space="  ", level=0)
tree.write(args.output, encoding="utf-8", xml_declaration=True)
print(f"✅ {args.output} erfolgreich erstellt.")