import os
import base64
from typing import Optional, Tuple, TypeAlias, Union
from math import log,sqrt
from dataclasses import dataclass
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont
import textlayout
from fontTools import ttLib
from pandas import DataFrame
from itertools import starmap

def encode_data_to_base64_uri(font_file_loc):
    with open(font_file_loc, "rb") as font_file:
        file_bytes=font_file.read()
    font_data_b64=base64.b64encode(file_bytes).decode("ascii")
    return f"data:application/x-font-ttf;base64,{font_data_b64}"



Dimensions: TypeAlias = tuple[int, int]
Margins: TypeAlias = tuple[int, int, int, int]

def kwarg_filter(kwargs, keys):
    subs = {"style_class" : "class"}
    return {subs.get(k,k):v for k,v in kwargs.items() if k in keys}

class SVGFontRegistry:

    def __init__(self, fonts : list[str]):
        self.fonts=fonts
        self.registry={}
        for f_path in fonts:
            if os.path.isfile(f_path) and f_path.endswith(".ttf"):
                font = ttLib.TTFont(f_path)
                self.registry[str(font['name'].names[4])]=SVGFont(f_path, str(font['name'].names[4]))

    def css_style(self)->str:
        # Emit style-formatted css code that encodes the fonts for wider use
        font_style=[]
        font_class_defs=[]
        for font_name, style, font_class_def in [(n,f.css_font_style_string(), f.css_class_string()) for n,f in self.registry.items()]:
            font_style.append(style)
            font_class_defs.append(font_class_def)
        
        return "\n".join(font_style) + "\n".join(font_class_defs)


class SVGFont:
    font_file_loc : str
    font_family_name : str

    def __init__(self, font_file_loc, font_family_name):
        self.font_file_loc=font_file_loc
        self.font_family_name=font_family_name
        self.font_class_name=f"font_{self.font_family_name.lower().replace(" ", "_")}"

    def css_font_style_string(self)->str:

        return f"""@font-face {{
                font-family:'{self.font_family_name}';
                src:url({encode_data_to_base64_uri(self.font_file_loc)}) format('truetype');
                }}
        """
    def css_class_string(self)->str:
        return f""".{self.font_class_name}{{font-family:'{self.font_family_name}';}}\n"""

    def getImageFont(self, fontsize)->ImageFont:
        return ImageFont.truetype(self.font_file_loc, fontsize)


class SVGElement:
    element:str
    attributes: dict
    content : str

    def __init__(self, 
                 element : str, 
                 attributes: dict,
                 content: str|None="%%placeholder%%"):
        self.element=element
        self.attributes = attributes
        self.content = "%%placeholder%%"        


    @property
    def width(self):
        return self.bounds[2]-self.bounds[0]

    @property
    def height(self):
        return self.bounds[3]-self.bounds[1]


    def __str__(self):
        attr_string = " ".join([f"{k}=\"{v}\"" for k,v in self.attributes.items()])
        return f"<{self.element} {attr_string}>{self.content}</{self.element}>"

class SVGTransformMatrix(SVGElement):
    def __init__(self, 
                 scale_x : float, 
                 skew_x : float, 
                 skew_y : float, 
                 scale_y : float, 
                 translate_x : float, 
                 translate_y : float):


        self.scale_x=scale_x 
        self.skew_x=skew_x 
        self.skew_y=skew_y 
        self.scale_y=scale_y 
        self.translate_x=translate_x 
        self.translate_y=translate_y 
        self.element="g"
        self.attributes={"transform" : f"matrix({scale_x},{skew_x},{skew_y},{scale_y},{translate_x},{translate_y})"}
        self.content = "%%placeholder%%"

    def _apply(self, x, y):
        x1 = (self.scale_x * x) + (self.skew_y * y) + self.translate_x
        y1 = (self.skew_x * x) + (self.scale_y * y) + self.translate_y
        return x1, y1

    @classmethod
    def to_location(cls, 
                    location : tuple[float, float]):
        x,y=location
        return SVGTransformMatrix(1, 0, 0, 1, x, y)
    
    @classmethod
    def from_bounds(cls, 
                    source_bounds, 
                    target_bounds):
        tlx_s,tly_s,brx_s,bry_s=source_bounds
        tlx_t,tly_t,brx_t,bry_t=target_bounds

        width_s = brx_s - tlx_s
        width_t = brx_t - tlx_t
        height_s = bry_s - tly_s
        height_t = bry_t - tly_t

        scale_x = width_t / width_s
        scale_y = height_t / height_s

        translate_x=tlx_t-(scale_x * tlx_s)
        translate_y=tly_t-(scale_y * tly_s)
        return SVGTransformMatrix(scale_x=scale_x,
                            skew_x=0, 
                            skew_y=0, 
                            scale_y=scale_y, 
                            translate_x=translate_x,
                            translate_y=translate_y)
    



class SVGViewBox(SVGElement):
    def __init__(self,
                 window_x : int, 
                 window_y : int, 
                 window_w : int, 
                 window_h : int, 
                 width : int, 
                 height : int):
        self.element='svg'
        self.attributes = {
            "xmlns":"http://www.w3.org/2000/svg",
            "viewBox" : f"{window_x} {window_y} {window_w} {window_h}",
            "width" : width, 
            "height" : height,
        }
        self.content = "%%placeholder%%"
        
class SVGStyle(SVGElement):
    def __init__(self, 
                 style_blocks : list[str],
                 ):
        self.element='style'
        self.attributes={
            "type" : "text/css"
        }
        self.content = "\n".join(style_blocks)

class SVGMultiLineText(SVGElement):
    def __init__(self, 
                 text : str, 
                 linespace : float,
                 font : SVGFont,
                 fontsize : int,
                 **kwargs):
        self.element='text'
        self.attributes={**
                         {
            "x" : 0, 
            "y" : 0,
            "style" : f"""font-family: {font.font_family_name}; font-size: {fontsize};""",
        }, **kwarg_filter(kwargs, {"style_class"})}
        self.layout=textlayout.TextMultiLine((0,0), text, linespace, font.getImageFont(fontsize))
        # Adjust bounds for text-height
        tlx,tly,brx,bry=self.layout.bounds
        self.bounds=tlx,tly,brx,bry

        if "title" in kwargs:
            optional_title = f"<title>{kwargs.get("title", "")}</title>"
        else:
            optional_title=""
        self.content=optional_title + self.layout._svg_stub(**kwargs)

class SVGDataGridLayout(SVGElement):
    def __init__(self,
                 frame : DataFrame, 
                 column_parameters : dict,
                 show_headers: bool,
                 headerfont: SVGFont, 
                 headerfontsize: int, 
                 datafont : SVGFont, 
                 datafontsize : int,
                 row_column_padding : tuple[int, int]):

        self.attributes={}
        self.element="g"
        if show_headers:
            header_row_adj=1
        else:
            header_row_adj=0
        self.row_count = len(frame)
        self.columns = frame.columns
        self.column_count = len(self.columns)
        max_row_height={}
        max_col_width={}
        rows=[]
        cells=[]
        if show_headers:
            r=0

            for c in range(0,self.column_count):
                if r not in max_row_height.keys():
                    max_row_height[r]=0
                if c not in max_col_width.keys(): # i.e. it's the first loop around (r=0)
                    max_col_width[c]=0
                data = "\n".join(textlayout.word_wrap(str(frame.columns[c]),35, " "))
                font=headerfont
                fontsize=headerfontsize
                linespace=1.0
                cell_content = SVGMultiLineText(data, linespace, font, fontsize)
                content_bounds = cell_content.bounds
                bounds_width=content_bounds[2]-content_bounds[0]
                bounds_height=content_bounds[3]-content_bounds[1]
                if bounds_width>max_col_width[c]:
                    max_col_width[c]=bounds_width
                if bounds_height>max_row_height[r]:
                    max_row_height[r]=bounds_height
        # The width of each column is equal to the width of the widest cell in that column, and the height of
        # each row is equal to the tallest cell in each row. 
                cells.append((cell_content, content_bounds,None))
            rows.append(cells)

        for r in range(0,self.row_count):
            if r+header_row_adj not in max_row_height.keys():
                max_row_height[r+header_row_adj]=0
            cells=[]
            for c in range(0,self.column_count):
                if c not in max_col_width.keys(): # i.e. it's the first loop around (r=0)
                    max_col_width[c]=0
                data = "\n".join(textlayout.word_wrap(str(frame.iloc[r,c]),35, " "))
                font=datafont
                fontsize=datafontsize
                linespace=1.0
                cell_content = SVGMultiLineText(data, linespace, font, fontsize)
                content_bounds = cell_content.bounds
                bounds_width=content_bounds[2]-content_bounds[0]
                bounds_height=content_bounds[3]-content_bounds[1]
                if bounds_width>max_col_width[c]:
                    max_col_width[c]=bounds_width
                if bounds_height>max_row_height[r+header_row_adj]:
                    max_row_height[r+header_row_adj]=bounds_height
        # The width of each column is equal to the width of the widest cell in that column, and the height of
        # each row is equal to the tallest cell in each row. 
                cells.append((cell_content, content_bounds,None))
            rows.append(cells)

        row_padding, column_padding = row_column_padding
        self.bounds = (0,
                       0,
                       sum(max_col_width.values())+(column_padding * (self.column_count-1)), 
                       sum(max_row_height.values())+(row_padding * (self.row_count-1)))
        
        full_width = self.bounds[2]-self.bounds[0]
        full_height = self.bounds[3]-self.bounds[1]
        row_padding = row_padding/full_width
        column_padding = column_padding/full_height

        row_loc=0
        for r in range(0,self.row_count+header_row_adj):
            col_loc=0
            for c in range(0,self.column_count):
                cell_width=max_col_width[c]/self.bounds[2]
                cell_height=max_row_height[r]/self.bounds[3]

                content, cell_bounds, transform = rows[r][c]

                natural_width = (cell_bounds[2]-cell_bounds[0])/self.bounds[2]
                natural_height=(cell_bounds[3]-cell_bounds[1])/self.bounds[3]
                
                cell_transform_group = SVGTransformMatrix.from_bounds(                        
                    cell_bounds, 
                    (col_loc*full_width,
                     row_loc*full_height,
                     (col_loc+natural_width)*full_width,
                     (row_loc+natural_height)*full_height))
                transformed_bounds=[v for q in (starmap(cell_transform_group._apply, 
                                                        [(x,y) for x,y in zip(cell_bounds[::2], cell_bounds[1::2])])) 
                                                        for v in q]

                rows[r][c]=(content, cell_bounds, cell_transform_group, transformed_bounds)

                col_loc=col_loc+cell_width+column_padding

            row_loc=row_loc+cell_height+row_padding

        b_br_x, b_br_y = 0,0
        for r in range(0,self.row_count+header_row_adj):
            for c in range(0,self.column_count):
                _,_,_,t_bounds=rows[r][c]
                if t_bounds[2]>b_br_x:
                    b_br_x=t_bounds[2]
                if t_bounds[3]>b_br_y:
                    b_br_y=t_bounds[3]
        self.bounds = (0,0,b_br_x,b_br_y)
        self.cells=[cel for row in rows for cel in row]
        grid_c=[]
        for cell,bounds,transform,transformed_bounds in self.cells:
            grid_c.append(str(transform).replace("%%placeholder%%", str(cell)))
        self.content = "\n".join([gc for gc in grid_c])


class SVGLine(SVGElement):
    def __init__(self, 
                 x1 : int, 
                 y1 : int, 
                 x2 : int, 
                 y2 : int, 
                 **kwargs):
        self.element="line"

        self.attributes={**{
            "x1":x1, 
            "y1":y1,
            "x2":x2, 
            "y2":y2}, **kwarg_filter(kwargs, {"style_class"})}

        self.content=""

class SVGRectangle(SVGElement):
    def __init__(self, 
                 x : int, 
                 y : int, 
                 width : int, 
                 height : int, 
                 rx : float, 
                 ry : float,
                 **kwargs):
        self.element="rect"

        self.attributes={**{
            "x":x, 
            "y":y,
            "width":width, 
            "height":height, 
            "rx":rx, 
            "ry":ry
        }, **kwarg_filter(kwargs, {"style_class"})}

        self.content=""

class SVGTitledPanelFromContent(SVGElement):
    """Defines a panel with a title-bar located at the top and contents provided by some SVGElement"""
    def __init__(self, 
                 identifier : str, 
                 title_text : str, 
                 title_font : SVGFont,
                 title_font_size : int, 
                 content_element : SVGElement,
                 corner_radii : tuple[int, int, int, int],
                 content_margins : tuple[int, int, int, int],
                 **kwargs
                 ):
        # Collate information necessary for sizing the panel
        # Note that in this form, the content (and title) 100% determine the final panel's size
        # There may be other generation methods where the panel dimensions are determined in 
        # a different way, with the content being resized/scaled to fit - that alternate form
        # of generation is not currently addressed here.
        title_text_element = SVGMultiLineText(title_text, 1.0, title_font, title_font_size) # n.b. consider hover/title text and/or a-href information
        f_ascent, f_descent=title_font.getImageFont(title_font_size).getmetrics()
        min_width=max([content_element.width+ sum([content_margins[0], content_margins[2]]), title_text_element.width])
        min_height=content_element.height + title_text_element.height + sum([content_margins[1] , content_margins[3]])

        panel_element = SVGSizedPanelOutline(identifier, 
                                       width=min_width, 
                                       height=min_height,
                                       title_bar_height=title_text_element.height,
                                       corner_radii=corner_radii,
                                       kwargs=kwargs
                                       )

        self.bounds=(0,0,min_width, min_height)
        self.element="g"

        content_element_transform = SVGTransformMatrix.to_location((content_margins[0], title_text_element.height + content_margins[1]))
        title_element_transform = SVGTransformMatrix.to_location((0, f_ascent))

        self.content=str(panel_element) + str(title_element_transform).replace("%%placeholder%%",str(title_text_element)) + str(content_element_transform).replace("%%placeholder%%", str(content_element))
        
        self.attributes={**{
            "id" : identifier
            }, **kwarg_filter(kwargs, {"style_class"})}


        
class SVGSizedPanelOutline(SVGElement):
    def __init__(
            self,
                identifier : str, 
                width : int, 
                height: int, 
                title_bar_height : int,
                corner_radii: tuple[int, int, int, int],
                **kwargs):
        self.element="g"
        tlr,trr,brr,blr=tuple([min([v,title_bar_height]) for v in corner_radii])
        x,y=(0,0)
        title_path = f"M {x} {y+(title_bar_height)} L {x} {y+tlr} Q {x} {y} {x+tlr} {y} L {x+width-trr} {y} Q {x+width} {y} {x+width} {y+trr} L {width+x} {y+title_bar_height} Z"
        canvas_path = f"M {x+width} {y+title_bar_height} L {x+width} {y+height-brr} Q {x+width} {y+height} {x+width-brr} {y+height} L {x+blr} {y+height} Q {x} {y+height} {x} {y+height-blr} L {x} {y+title_bar_height} Z"    
        self.content=f"""<path d="{title_path}" stroke="black" stroke-width="1px" fill="pink" opacity="1.00" />""" +\
        f"""<path d="{canvas_path}" stroke="black" stroke-width="1px" fill="white" opacity="1.00" />"""

        self.attributes={**{
            "id" : identifier
            }, **kwarg_filter(kwargs, {"style_class"})}


class SVGTitledPanel(SVGElement):
    """Defines a panel with a title-bar located at the top - old version with tricky scaling"""
    def __init__(self, 
                 identifier : str, 
                 width : int, 
                 height: int, 
                 text: str, 
                 corner_radii: tuple[int, int, int, int],
                 font : SVGFont,
                 **kwargs):

        x,y=0,0
        title_bar_height = 16
        canvas_height = height - 16
        tlr,trr,brr,blr=tuple([min([v,title_bar_height]) for v in corner_radii])
        title_path = f"M {x} {y+(title_bar_height)} L {x} {y+tlr} Q {x} {y} {x+tlr} {y} L {x+width-trr} {y} Q {x+width} {y} {x+width} {y+trr} L {width+x} {y+title_bar_height} Z"
        canvas_path = f"M {x+width} {y+title_bar_height} L {x+width} {y+height-brr} Q {x+width} {y+height} {x+width-brr} {y+height} L {x+blr} {y+height} Q {x} {y+height} {x} {y+height-blr} L {x} {y+title_bar_height} Z"
        title_text = SVGMultiLineText(text, 1.0, font, 16, **kwargs)
        f_ascent, f_descent=font.getImageFont(16).getmetrics()
        f_height = f_ascent + f_descent
        title_text_aspect_ratio=(title_text.bounds[2]-title_text.bounds[0])/(title_text.bounds[3]-title_text.bounds[1])
        target_text_bounds=(0+(tlr-sqrt(tlr/2)), 0, width-(trr-sqrt(trr/2)), title_bar_height)
        target_text_aspect_ratio=(target_text_bounds[2]-target_text_bounds[0])/(target_text_bounds[3]-target_text_bounds[1])
        print(title_text_aspect_ratio, target_text_aspect_ratio)
        text_transform = SVGTransformMatrix.from_bounds(title_text.bounds, target_text_bounds)
        self.element="g"
        self.content=f"""<path d="{title_path}" stroke="black" stroke-width="1px" fill="pink" opacity="1.00" />""" +\
        f"""<path d="{canvas_path}" stroke="black" stroke-width="1px" fill="white" opacity="1.00" />""" +\
        str(text_transform).replace("%%placeholder%%", str(title_text))

        self.attributes={**{
            "id" : identifier
            }, **kwarg_filter(kwargs, {"style_class"})}


class SVGDebugLayoutGrid(SVGElement):
    """Defines a background of measurement lines laid out in a grid over which objects can be located"""
    def __init__(self, 
                 identifier : str,
                 x : int, 
                 y : int, 
                 width : int, 
                 height : int, 
                 gridcolour : str,
                 grid_x_range_partitions : tuple[int, int, int],
                 grid_y_range_partitions : tuple[int, int, int],
                 axes_font: SVGFont, 
                 axes_font_size : str,
                 margins : Margins,
                 **kwargs
                 ):
        self.element="g"
        self.attributes={**{"id":identifier}, **kwarg_filter(kwargs, {"class"})}
        outer_rectangle=SVGRectangle(x=0, 
                                     y=0,
                                     width=width,
                                     height=height,
                                     rx=0,
                                     ry=0, 
                                     style_class="layout_rect")

        inner_rectangle=SVGRectangle(x=margins[0], 
                                     y=margins[1],
                                     width=width-(margins[0]+margins[2]),
                                     height=height-(margins[1]+margins[3]),
                                     rx=0,
                                     ry=0, 
                                     style_class="layout_line")
        
        diagonal=SVGLine(x1=margins[0], 
                                     y1=margins[1],
                                     x2=width-margins[2],
                                     y2=height-margins[3],
                                     style_class="layout_line")

        scale_x=(width-(margins[0]+margins[2]))/(grid_x_range_partitions[1]-grid_x_range_partitions[0])
        scale_y=(height-(margins[1]+margins[3]))/(grid_y_range_partitions[1]-grid_y_range_partitions[0])
        cell_width=(grid_x_range_partitions[1]-grid_x_range_partitions[0])/(grid_x_range_partitions[2])
        cell_height=(grid_y_range_partitions[1]-grid_y_range_partitions[0])/(grid_y_range_partitions[2])

        layout_lines=[]
        grid_axes_ticklabels=[]
        for v_lines in range(0,grid_x_range_partitions[2]+1):
            layout_lines.append(SVGLine(x1=margins[0]+(cell_width*v_lines*scale_x), 
                                        y1=margins[1],
                                        x2=margins[0]+(cell_width*v_lines*scale_x),
                                        y2=height-margins[3],
                                        style_class="layout_line"))


        for h_lines in range(0,grid_y_range_partitions[2]+1):
            layout_lines.append(SVGLine(x1=margins[0], 
                                        y1=margins[1]+(cell_height*h_lines*scale_y),
                                        x2=width-margins[2],
                                        y2=margins[1]+(cell_height*h_lines*scale_y),
                                        style_class="layout_line"))
            
        blocks =[
                outer_rectangle
                ]
        
        blocks.extend(layout_lines)
        
        self.content="\n".join([
            str(s) for s in blocks
        ])
        
