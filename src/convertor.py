# This is a sample Python script.
import dataclasses
import typing
from dataclasses import dataclass, field
import ezdxf
import numpy as np
from ezdxf.enums import TextEntityAlignment
import shapely
from shapely.geometry import mapping
from mmcore.geom.parametric import algorithms
from mmcore.geom.shapes.shape import Contour, ShapeInterface, poly_to_shapes, ContourShape

HATCH_TYPES = {'inner': ezdxf.const.HATCH_STYLE_IGNORE, 'outer': ezdxf.const.HATCH_STYLE_OUTERMOST}


class Visitable:
    def accept(self, visitor):
        lookup = "visit_" + type(self).__qualname__.replace(".", "_").lower()
        return getattr(visitor, lookup)(self)


@dataclass
class DxfText(Visitable):
    text: str = 'A'
    high: float = 100.0
    style: str = "CXM"
    align: str = "MIDDLE_CENTER"
    layer: str = "CXM_Text"
    color: typing.Optional[int] = None

    def __post_init__(self):
        self.dxfattribs = dict(
            layer=self.layer

        )
        if self.color is not None:
            self.dxfattribs['color'] = self.color

    def convert(self, origin, msp):
        text = msp.add_text(
            self.text,
            height=self.high,
            dxfattribs=self.dxfattribs
        )
        # print(origin)
        text.set_placement(
            origin,
            align=TextEntityAlignment[self.align]
        )

        return text


@dataclass
class DXFObjectColorPalette:
    lines: int = 0
    hatch: int = 254
    text: int = 33


dxfentities = []


@dataclass
class DxfHatch(Visitable):
    ...


@dataclass
class DxfShape(Visitable):
    shape: 'Panel'
    fill: typing.Optional[str] = None
    text: typing.Optional[DxfText] = None
    color: DXFObjectColorPalette = dataclasses.field(default_factory=DXFObjectColorPalette)
    layer: str="CXM_Contour"
    def __post_init__(self):
        dxfentities.append(self)

    def convert(self, msp):

        # for shapes
        self.create_polylines(msp)

    def create_polylines(self, msp):
        # for shapes
        if self.shape.split_result.mask != 2:

            for sh in self.shape.split_result.shapes:
                hs = [pt[:2] for pt in sh.bounds]

                msp.add_lwpolyline(hs, dxfattribs={"layer": f"CXM_{self.shape.tag}_Contour"})

    def create_text(self, origin, msp):

        if self.text is not None:

            for shp in self.shape.split_result.shapes:
                pl = shp.to_poly()
                if not pl.contains(shapely.Point(*origin)):
                    msp.add_leader([origin,
                                    list(shp.to_poly().centroid.coords)[0][:2]],
                                   '',
                                   dxfattribs={"layer": f"CXM_{self.shape.tag}_Text"})

            return self.text.convert(origin, msp)

    def create_hatches(self, shapes, msp):
        if self.fill:
            hatch = msp.add_hatch(
                color=self.color.hatch,
                dxfattribs={
                    "layer": f"CXM_{self.shape.tag}_Hatch",
                    "hatch_style": ezdxf.const.HATCH_STYLE_NESTED,
                    # 0 = nested: ezdxf.const.HATCH_STYLE_NESTED
                    # 1 = outer: ezdxf.const.HATCH_STYLE_OUTERMOST
                    # 2 = ignore: ezdxf.const.HATCH_STYLE_IGNORE
                },
            )

            for sh in shapes:
                hatch.paths.add_polyline_path(
                    [bmd[:2] for bmd in sh.bounds],
                    is_closed=True,
                    flags=ezdxf.const.BOUNDARY_PATH_EXTERNAL,
                )
                if sh.holes:
                    for hole in sh.holes:
                        hatch.paths.add_polyline_path(
                            [pt[:2] for pt in hole],
                            is_closed=True,
                            flags=ezdxf.const.BOUNDARY_PATH_OUTERMOST,
                        )


@dataclass
class Panel(ShapeInterface, Visitable):
    color: DXFObjectColorPalette = dataclasses.field(default_factory=DXFObjectColorPalette)
    text: typing.Optional[DxfText] = None
    tag: str = "A0"
    fill: typing.Optional[str] = None
    split_result_hatch: typing.Optional[list[ShapeInterface]] = field(default_factory=list)

    def __post_init__(self):

        self.bound_convertor = DxfShape(
            self,
            fill=None,
            text=self.text,
            color=self.color
        )

        self.hatch_shape = None
        if self.fill:
            if self.fill == "inner":

                self.hatch_shape = poly_to_shapes(self.hatch_hole())

            elif self.fill == "outer":

                self.hatch_shape = poly_to_shapes(shapely.Polygon(self.bounds) - self.hatch_hole().buffer(-0.01))
            elif self.fill == "full":

                self.hatch_shape = poly_to_shapes(shapely.Polygon(self.bounds))

            else:
                raise "Hatch Attension"

            self.hatch_convertor = DxfShape(
                self,
                fill=self.fill,
                color=self.color,

            )

    def hatch_hole(self):

        a, b, c = self.bounds

        return shapely.Polygon([algorithms.centroid(np.array([a, b])).tolist(),
                                algorithms.centroid(np.array([b, c])).tolist(),
                                algorithms.centroid(np.array([c, a])).tolist()])

    def split(self, cont: Contour):

        self.split_result = super().split(cont)
        if self.fill:

            for sh in self.hatch_shape:
                # print(sh)
                r = sh.split(cont)
                if r.mask != 2:
                    self.split_result_hatch.extend(r.shapes)

    def convert(self, msp):

        if self.split_result.mask != 2:
            self.bound_convertor.convert(msp)
            self.bound_convertor.create_text(list(self.to_poly().centroid.coords)[0][:2], msp)

            if self.fill is not None:
                self.hatch_convertor.create_hatches(self.split_result_hatch, msp)


class DxfPanelExporter:
    def __init__(self, path="test.dxf", version="R2018", setup=True, layers=()):
        self.doc = ezdxf.new(dxfversion=version, setup=setup)
        self.msp = self.doc.modelspace()
        self.path = path
        self.doc.styles.new("CXM", dxfattribs={"font": "Arial"})
        self.doc.layers.add("CXM_Contour", color=251)
        self.doc.layers.add("CXM_Text", color=251)
        for lay in layers:
            self.doc.layers.add(**lay)

    def __enter__(self):
        return self

    def __call__(self, shapes: list[Panel], contour: Contour):
        for o in shapes:
            o.split(cont=contour)
            o.convert(self.msp)
        return self.doc, self.msp

    def __exit__(self, exc_type, *args):
        name, ext = self.path.split(".")
        print(exc_type, *args)
        self.doc.saveas(f'{name}_error.dxf')
