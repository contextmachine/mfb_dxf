import os
import json
import requests
import dotenv
dotenv.load_dotenv('.env')
from mmcore.services.redis.connect import get_cloud_connection
from mmcore.services.redis import sets
from src.cxm_props import BLOCK, PROJECT, ZONE
from src.convertor import *

with open('styles.json') as fl:
    import json

    props = json.load(fl)

rconn = get_cloud_connection()
rd_a = f"{PROJECT}:{os.getenv('REDIS_HSET_NAME')}:{BLOCK}"


def contour_from_dict(data: dict):
    return Contour([ContourShape(**shp) for shp in data['shapes']], data['plane'])


def update_dxf_style_sheet(data: dict, contour_server_address_project=PROJECT) -> dict:
    redis_styles_sheet = sets.Hdict(f"{contour_server_address_project}:dxf:styles_sheet")
    for k, v in data.items():
        redis_styles_sheet[k] = v
    return dict(redis_styles_sheet)


def convert(grid_service_address=f"{os.getenv('GRID_URL')}/stats",
            styles_from_redis=False,
            styles_file='styles.json',
            contour_server_address_name=ZONE,
            contour_server_address_block=BLOCK,
            contour_server_address_project=PROJECT,

            ):
    panels_dict = {}
    if styles_from_redis:
        styles_sheet = dict(sets.Hdict(f"{contour_server_address_project}:dxf:styles_sheet"))


    else:
        with open(styles_file) as f:
            styles_sheet = json.load(f)

    contour_server_address = f"{contour_server_address_project}:{os.getenv('REDIS_HSET_NAME')}:{contour_server_address_block}"
    untrim_panels = sets.Hdict(contour_server_address)
    panels = untrim_panels['panels'][contour_server_address_name]
    names = untrim_panels['names'][contour_server_address_name]
    contours = untrim_panels['contours'][contour_server_address_name]
    cont = contour_from_dict(contours)
    untrim_panels = dict(zip(names, panels))

    tags = requests.get(grid_service_address)
    tags = tags.json()

    for i in tags:

        if i['cut'] != 2:

            if len(i['name'].split('_')) > 6:

                name = "_".join(i['name'].split('_')[:-1])
                print(name, 'pair')
            else:
                name = i['name']

            if name not in panels_dict.keys():

                panels_dict[name] = {'panel': untrim_panels[name],
                                     'tag': str(i['arch_type']) + str(i['eng_type'])}
            else:
                print(name)

    layys = []
    lyy = []

    ppp = []
    for name, pnl in panels_dict.items():
        tag = pnl['tag']
        stats = styles_sheet[pnl['tag']]
        hatch_color = 0 if stats['hatches'] is None else stats['hatches']

        if tag not in layys:
            lyy.append(dict(name=f"CXM_{tag}_Hatch", color=hatch_color))
            lyy.append(dict(name=f"CXM_{tag}_Contour", color=stats['lines']))
            lyy.append(dict(name=f"CXM_{tag}_Text", color=stats['text']))
            layys.append(tag)
        ppp.append(Panel(pnl['panel'],
                         fill=stats['fill'],
                         text=DxfText(text=stats['tag'], layer=f"CXM_{tag}_Text"),
                         tag=tag,
                         color=DXFObjectColorPalette(lines=stats['lines'],
                                                     hatch=hatch_color,
                                                     text=stats['text'])))

    with DxfPanelExporter(path="test1.dxf", setup=True, layers=lyy) as exporter:
        doc, msp = exporter(ppp, cont)
    return doc, msp


import click


@click.command()
@click.argument('filename')
@click.option('--stats', default=f"{os.getenv('GRID_URL')}/stats", help='Grid service stats url')
@click.option('--styles-from-redis', is_flag=True, default=0, help='Get styles from redis. If exist, '
                                                                   '--styles option will be ignored')
@click.option('--styles', default='styles.json', help='Path to styles JSON file.')
@click.option('--project', default=PROJECT, help='Project name')
@click.option('--block', default=BLOCK, help='Project block name')
@click.option('--zone', default=ZONE, help='Name for zone in block')
def cli(filename, stats, styles_from_redis, styles, project, block, zone):
    print(styles_from_redis)
    doc, mps = convert(grid_service_address=stats,
                       styles_from_redis=styles_from_redis,
                       styles_file=styles,
                       contour_server_address_project=project,
                       contour_server_address_block=block,
                       contour_server_address_name=zone)
    doc.saveas(filename)

if __name__ == '__main__':
    cli()