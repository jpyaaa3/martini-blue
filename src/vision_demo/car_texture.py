"""Bake six orthographic paint panels for the existing low-poly car.

Run python -m vision_demo.car_texture. Geometry remains unchanged; wheels are
painted side details because the source model has no separate wheel geometry.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

SIZE = 512


def build_car(asset_dir: Path):
    vertices, faces = [], []
    for line in (asset_dir/'car.obj').read_text().splitlines():
        if line.startswith('v '):
            vertices.append([float(v) for v in line.split()[1:4]])
        elif line.startswith('f '):
            faces.append([int(v.split('/')[0])-1 for v in line.split()[1:]])
    vertices = np.asarray(vertices)
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    atlas = Image.new('RGB', (SIZE*3, SIZE*2), '#174b87')
    # Panels: +/-X, +/-Y, +/-Z. An inset provides a filtering gutter.
    for panel in range(6):
        tile = Image.new('RGB', (SIZE,SIZE), '#2065a5')
        draw = ImageDraw.Draw(tile)
        def point(a,b):
            return (16+a*480,16+(1-b)*480)
        def rect(a,b,c,d,fill,outline=None,width=1):
            draw.rectangle((*point(a,d),*point(c,b)), fill=fill, outline=outline, width=width)
        if panel in (2,3):
            # World X horizontal and Z vertical. +X is vehicle forward.
            rect(0,0,1,.17,'#14202c')
            rect(.08,.30,.94,.33,'#a5bed0')
            rect(.345,.59,.965,.965,'#101d2a', '#0c2338',5)
            rect(.36,.62,.59,.93,'#426981')
            rect(.62,.62,.95,.93,'#426981')
            for x in (.595,.965):
                rect(x,.19,x+.008,.58,'#123c64')
            rect(.52,.49,.57,.505,'#c1d1df')
            rect(.88,.49,.93,.505,'#c1d1df')
            for x in (.16,.81):
                cx,cy = point(x,.13)
                # X/Z have unequal physical spans: compensate so wheels look round.
                rx,ry = 44,44*6/3.5
                draw.ellipse((cx-rx,cy-ry,cx+rx,cy+ry),fill='#101318',outline='#303a43',width=5)
                draw.ellipse((cx-rx*.57,cy-ry*.57,cx+rx*.57,cy+ry*.57),fill='#9aa9b3',outline='#566672',width=4)
                draw.ellipse((cx-7,cy-12,cx+7,cy+12),fill='#263442')
            rect(.965,.30,1,.43,'#e8f4ff')
            rect(0,.30,.045,.43,'#b82431')
        elif panel in (0,1):
            rect(0,0,1,.08,'#15202c')
            rect(.12,.09,.88,.17,'#101921')
            for y in (.11,.135,.16):
                rect(.15,y,.85,y+.006,'#708293')
            color = '#eff8ff' if panel == 0 else '#bc2836'
            rect(.05,.19,.28,.27,color, '#122638',3)
            rect(.72,.19,.95,.27,color, '#122638',3)
            rect(.36,.10,.64,.16,'#d9e1e5')
            rect(.34,.60,.66,.965,'#172b3d')
            rect(.355,.625,.645,.94,'#476b80')
        elif panel == 4:
            rect(.06,.36,.94,.64,'#164774')
            rect(.11,.40,.88,.60,'#337bb7')
        else:
            tile.paste('#18222c',(0,0,SIZE,SIZE))
        atlas.paste(tile, ((panel%3)*SIZE,(panel//3)*SIZE))
    lines = ['mtllib car_textured.mtl','o car','usemtl car_atlas']
    uv, normals, indices = [], [], []
    lines.extend('v %.6f %.6f %.6f' % tuple(v) for v in vertices)
    for face in faces:
        points = vertices[face]
        normal = np.cross(points[1]-points[0],points[2]-points[0])
        normal /= np.linalg.norm(normal)
        axis = int(np.argmax(np.abs(normal)))
        panel = axis*2 + int(normal[axis]<0)
        # Sloped roof/windshield faces use X-end panels for glazing.
        axes = ((1,2),(0,2),(0,1))[axis]
        indices.append([])
        for vertex in face:
            p = (vertices[vertex]-low)/(high-low)
            px = panel%3*SIZE+16+p[axes[0]]*480
            py = panel//3*SIZE+16+(1-p[axes[1]])*480
            uv.append((px/(SIZE*3),1-py/(SIZE*2)))
            normals.append(normal)
            indices[-1].append((vertex+1,len(uv)))
    lines.extend('vt %.9f %.9f' % p for p in uv)
    lines.extend('vn %.9f %.9f %.9f' % tuple(n) for n in normals)
    lines.extend('f '+' '.join(f'{v}/{i}/{i}' for v,i in face) for face in indices)
    atlas.save(asset_dir/'car_texture.png')
    (asset_dir/'car_textured.obj').write_text('\n'.join(lines)+'\n')
    (asset_dir/'car_textured.mtl').write_text('newmtl car_atlas\nKd 1 1 1\nKs 0.2 0.2 0.2\nNs 32\nd 1\nmap_Kd car_texture.png\n')


if __name__ == '__main__':
    build_car(Path(__file__).with_name('assets'))
