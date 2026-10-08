from typing import Optional, Tuple
from math import log
from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass
from abc import ABC, abstractmethod


def word_wrap(text_block : str, 
                        max_target_length : int, 
                        favoured_break_chars : str
                       ) -> list[str]:
    """Reading in text-blocks, and instering line-breaks into those
    blocks where the cumulative line-length exceeds some target. 
    It's possible that a series of blocks will be fed, requiring
    some cumulative line-length calculation to be managed."""
    linebreaks=[]
    lines=[]
    last_cut=0
    while len(text_block[last_cut:].strip())>0:
        scores={}
        for e,c in enumerate(text_block[last_cut:]):
            if c in favoured_break_chars:
                adj=1.5
            else:
                adj=0
            if e<max_target_length:
                scores[e]=log(e+1)+adj
            else:
                scores[e]=0
                break
        if scores[e]==0:
            best=sorted([(k,v) for k,v in scores.items()], key=lambda x:x[1], reverse=True)[0][0]
            #print(e, scores.values())
        else:
            best=len(text_block[last_cut:])
        
        lines.append([last_cut,last_cut+best+1])
        last_cut = last_cut+best+1
    return lines


class DrawComponent(ABC):

    @abstractmethod
    def _bounds(self)->tuple[float, float, float, float]:
        """Calculate the coordinates (top-left, bottom-right) of the 
        bounding box that encompasses this object"""
        return NotImplemented

    @abstractmethod
    def _pillow_draw(self, drawing_object, **kwargs):
        """Code to implement the visualisation of this object within
        a pillow drawing_object's context"""
        return NotImplemented

class TextMultiSpan(DrawComponent):
    def __init__(self, 
                pos : tuple[int, int],
                span_markup : list[list[tuple[str,dict[dict]]]],
                linespace : int,
                font : ImageFont):
        self.pos=pos
        self.font=font
        sample_t = TextSpan(pos, "Hg", font)
        positions=[]
        
        x_position=pos[0]
        self.text_spans=[]
        for r,row_c in enumerate(span_markup):
            positions.append([])
            y_position=pos[1]+(sample_t.lineheight*r*linespace)
            last_bb = (0,0,0,0)
            for c,cel_c in enumerate(row_c):
                x_position=last_bb[2]
                cel_text, cel_style_d = cel_c
                cel_text=cel_text.replace("\n","")
                positions[r].append([])
                # Position values to be stored as (x,y) tuples
                t_span=TextSpan((x_position,y_position), cel_text, font, cel_style_d)
                self.text_spans.append(
                    t_span
                )
                last_bb=t_span._bounds()
        self.bounds=self._bounds()
        left, top, right, bottom = self.bounds
        self.width=right-left
        self.height=bottom-top
        self.aspect_ratio=self.width/self.height

    def _bounds(self):
        all_bounds = [tl._bounds() for tl in self.text_spans]
        x0,y0=min([b[0] for b in all_bounds]), min([b[1] for b in all_bounds])
        x1,y1=max([b[2] for b in all_bounds]), max([b[3] for b in all_bounds])
        return x0,y0,x1,y1

    def _svg_stub(self, **kwargs):
        spans=[span._svg_stub(**kwargs) for span in self.text_spans]
        return "\n".join(spans)

    
    def _pillow_draw(self, drawing_object, **kwargs):
            
        if 'block' in kwargs.keys():
            bounds=self._bounds()
            drawing_object.rectangle(
                [*bounds],
                outline=kwargs['block'],
                width=1,
                fill=kwargs['block']
            )

        scale_x, scale_y = 100/self.width, 100/self.height
        
        for tl in self.text_lines:
            tl._pillow_draw(drawing_object)



class TextMultiLine(DrawComponent):
    """Accepts raw text, splits it based on \n characters and 
    models the result."""

    def __init__(self, 
                 pos : tuple[int, int],
                 text : str,
                 linespace : int,
                 font : ImageFont):
        self.pos=pos
        self.text=text
        self.font=font

        sample_t = TextSpan(pos, "Hg", font)

        # Simple placement of textlines one atop one another based on
        # line height and linespace parameters - left-aligned, only y-pos calculated from 
        # line sequence
        self.text_lines = [TextSpan((pos[0],pos[1]+(sample_t.lineheight*e*linespace)), 
                          t, 
                          font) for e,t in enumerate(text.split("\n"))]

        self.bounds=self._bounds()
        left, top, right, bottom = self.bounds
        self.width=right-left
        self.height=bottom-top
        self.aspect_ratio=self.width/self.height

    def _bounds(self):
        all_bounds = [tl._bounds() for tl in self.text_lines]
        x0,y0=min([b[0] for b in all_bounds]), min([b[1] for b in all_bounds])
        x1,y1=max([b[2] for b in all_bounds]), max([b[3] for b in all_bounds])
        return x0,y0,x1,y1

    def _svg_stub(self, **kwargs):
        spans=[span._svg_stub(**kwargs) for span in self.text_lines]
        return "\n".join(spans)

    
    def _pillow_draw(self, drawing_object, **kwargs):
            
        if 'block' in kwargs.keys():
            bounds=self._bounds()
            drawing_object.rectangle(
                [*bounds],
                outline=kwargs['block'],
                width=1,
                fill=kwargs['block']
            )

        scale_x, scale_y = 100/self.width, 100/self.height
        
        for tl in self.text_lines:
            tl._pillow_draw(drawing_object)


class TextSpan(DrawComponent):
    
    def __init__(self, 
                 pos : tuple[int, int],
                 text : str,
                 font : ImageFont, 
                 style_dict : dict[str,dict] | None = None) :
        self.pos=pos
        self.text=text
        self.font=font

        self.is_bold = False
        self.is_italic = False
        self.is_link = False
        self.is_super = False
        self.is_sub = False

        self.bounds=self._bounds()
        left, top, right, bottom = self.bounds
        self.lineheight = bottom - top
        self.width=right-left
        self.height=bottom-top
        self.aspect_ratio=self.width/self.height


        if style_dict is not None:
            if "bold" in style_dict.keys():
                self.is_bold=True
            if "italic" in style_dict.keys():
                self.is_italic=True
            if "link" in style_dict.keys():
                self.is_link=True
            if "super" in style_dict.keys():
                self.is_super=True
            if "sub" in style_dict.keys():
                self.is_sub=True
        self.style_dict=style_dict

    def _bounds(self):
        x,y=self.pos
        fm_ascent, fm_descent = self.font.getmetrics()
        font_measure_width = self.font.getlength(self.text)
        average_char_width = font_measure_width/len(self.text)
        # Adjust bounds based on style variations
        if self.is_bold or self.is_italic:
            font_measure_width=font_measure_width + (0.7 * average_char_width) # Naieve adjustment - needs better method

        return (x, y-fm_ascent, x+font_measure_width, y+fm_descent)

    def _svg_stub(self, **kwargs):
        x,y=self.pos
        extra_styles="xml:space=\"preserve\""
        # Optional Bold/Italic Styling
        for extra in ['is_italic', 'is_bold']:
            if getattr(self, extra):
                if extra=="is_italic":
                    extra_styles=" ".join([extra_styles, "font-style=\"italic\""])
                if extra=="is_bold":
                    extra_styles=" ".join([extra_styles, "font-weight=\"bold\""])
        for extra in ['is_super', 'is_sub']:
            if getattr(self, extra):
                if extra=="is_super":
                    extra_styles=" ".join([extra_styles, "baseline-shift=\"super\""])
                if extra=="is_sub":
                    extra_styles=" ".join([extra_styles, "baseline-shift=\"sub\""])
        for extra in ['is_link']:
            if getattr(self, extra):
                extra_styles=" ".join([extra_styles, "text-decoration=\"underline\""])


        # Optional Link Wrapping
        link_wrapper_open=""
        link_wrapper_close=""
        if self.is_link:
            link_d = self.style_dict.get("link")
            title=link_d.get("title")
            target=link_d.get("target")
            link_title = f"title=\"{title}\""
            link_target=f"target=\"{target}\""
            if title is None:
                link_title=""
            if target is None:
                link_target=""

            link_wrapper_open=" ".join([f"<a href=\"{link_d.get("href")}\"" ,
                                        link_title, 
                                        link_target,
                                        ">"])
            link_wrapper_close="</a>"

        return f"""{link_wrapper_open}<tspan x="{x}" y="{y}" {extra_styles}>{self.text}</tspan>{link_wrapper_close}"""

    def _pillow_draw(self, drawing_object, **kwargs):
        if 'anchor' not in kwargs.keys():
            kwargs['anchor']='ls'
        if 'fill' not in kwargs.keys():
            kwargs['fill']='black'
        x,y=self.pos
        print(self.pos, self.bounds)
        bounds=self._bounds()
        if 'highlight' in kwargs.keys():
            drawing_object.rectangle(
                [*bounds],
                outline=kwargs['highlight'],
                width=1,
                fill=kwargs['highlight']
            )
        if 'baseline' in kwargs.keys():
            drawing_object.line([x, y,bounds[2], y],
                 fill=kwargs['baseline'], width=5)
        
        drawing_object.text((x,y), 
                            self.text, 
                            font=self.font, 
                            fill=kwargs['fill'], 
                            anchor=kwargs['anchor'])


class LayoutFrame(DrawComponent):

    def __init__(self, 
                 width : int, 
                 height : int, 
                 padding : int, 
                 x_gridsize : int, 
                 y_gridsize : int, 
                 font : ImageFont, 
                 text_color : tuple[int, int, int],
                 axis_color  : tuple[int, int, int] ):

        self.padding=padding
        self.width=width
        self.height=height
        self.x_gridsize=x_gridsize
        self.y_gridsize=y_gridsize
        self.cell_height=int(height/y_gridsize)
        self.cell_width=int(width/x_gridsize)
        self.font=font
        self.text_color=text_color
        self.axis_color=axis_color
        self.bounds=self._bounds()
        
    def _bounds(self):
        return (self.padding, self.padding, self.width, self.height)
    
    def _pillow_draw(self, drawing_object, **kwargs):
        # Draw padding rectangle
        drawing_object.rectangle(
            [0, 0, self.width+(2*self.padding), self.height+(2*self.padding)],
            outline="red",
            width=1,
        )
        #Draw horizontal gridlines
        for i in range(0,self.y_gridsize+1):
            y = i*self.cell_height
            drawing_object.text((self.padding, y+self.padding), str(y), font=self.font, fill=self.text_color, anchor='rm')
            drawing_object.line([(self.padding, y+self.padding), (self.padding + self.width, y+self.padding)], fill=self.axis_color, width=2)
            
        
        for i in range(0,self.x_gridsize+1):
            x = i*self.cell_width
            drawing_object.line([(x+self.padding, self.padding), (x+self.padding, self.padding+self.height)], fill=self.axis_color, width=2)
            drawing_object.text((x+self.padding, self.padding), str(x), font=self.font, fill=self.text_color, anchor='ms')