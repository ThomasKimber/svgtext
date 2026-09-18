from typing import Optional, Tuple
from math import log
from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass
from abc import ABC, abstractmethod




def word_wrap(line : str, 
              target : int, 
              bchars : str) -> list[str]:
    """Convert input text and a target char
    count into a list of shortened text lines
    favouring break-points where a character
    matches any of the chars provided in bchars"""
    linebreaks=[]
    lines=[]
    progress=0
    while len(line.strip())>0:
        scores={}
        for e,c in enumerate(line):
            progress=e
            if c in bchars:
                adj=1
            else:
                adj=0
            if e<target:
                scores[e]=log(e+1)+adj
            else:
                scores[e]=0
                break
        if scores[e]==0:
            best=sorted([(k,v) for k,v in scores.items()], key=lambda x:x[1], reverse=True)[0]
            print(best, progress)
        else:
            best=[len(line),0]
        linebreaks.append(best[0])
        lines.append(line[:best[0]])
        line=line[best[0]:]
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


class TextMultiLine(DrawComponent):

    def __init__(self, 
                 pos : tuple[int, int],
                 text : str,
                 linespace : int,
                 font : ImageFont):
        self.pos=pos
        self.text=text
        self.font=font

        sample_t = TextLine(pos, "Hg", font)

        self.text_lines = [TextLine((pos[0],pos[1]+(sample_t.lineheight*e*linespace)), 
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


class TextLine(DrawComponent):
    
    def __init__(self, 
                 pos : tuple[int, int],
                 text : str,
                 font : ImageFont) :
        self.pos=pos
        self.text=text
        self.font=font
        self.bounds=self._bounds()
        left, top, right, bottom = self.bounds
        self.lineheight = bottom - top
        self.width=right-left
        self.height=bottom-top
        self.aspect_ratio=self.width/self.height
        

    def _bounds(self):
        x,y=self.pos
        fm_ascent, fm_descent = self.font.getmetrics()
        font_measure_width = self.font.getlength(self.text)
        return (x, y-fm_ascent, x+font_measure_width, y+fm_descent)

    def _svg_stub(self, **kwargs):
        x,y=self.pos
        return f"""<tspan x="{x}" y="{y}" >{self.text}</tspan>"""

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