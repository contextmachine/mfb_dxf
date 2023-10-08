import os
import json
import requests

from mmcore.services.redis.connect import get_cloud_connection
from mmcore.services.redis import sets
from src.cxm_props import BLOCK, PROJECT, ZONE

panels_dict = {}

rconn = get_cloud_connection()
redis_address=f"{PROJECT}:{BLOCK}:{os.getenv('REDIS_HSET_NAME')}"

untrim_panels = sets.Hdict(redis_address)
panels=untrim_panels['panels'][ZONE]
names=untrim_panels['names'][ZONE]
contours=untrim_panels['contours'][ZONE]

untrim_panels = dict(zip(names, panels))

tags = requests.get(f"{os.getenv('GRID_URL')}/stats")
tags = tags.json()

for i in tags:

    if i['projmask'] != 2:

        if len(i['name'][20:].split('_')) > 3:
            name = i['name'][:-2]
            print(name, 'pair')
        else:
            name = i['name']

        if name not in panels_dict.keys():
            panels_dict[name] = {'panel': untrim_panels[name],
                                 'tag': str(i['arch_type'])+str(i['eng_type'])}
        else:
            print(name)
