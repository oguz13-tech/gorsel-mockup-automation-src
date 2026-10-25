"""Pure canvas viewport math (never changes source pixels or annotations)."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Viewport:
    width: int
    height: int
    canvas_width: int
    canvas_height: int
    scale: float = 1.
    offset_x: float = 0.
    offset_y: float = 0.
    fit_scale: float = 1.

    def __post_init__(self):
        self.fit()

    def fit(self):
        self.fit_scale = min(1., max(1,self.canvas_width-16)/self.width,
                             max(1,self.canvas_height-16)/self.height)
        self.scale = self.fit_scale
        self.offset_x = (self.canvas_width - self.width*self.scale)/2
        self.offset_y = (self.canvas_height - self.height*self.scale)/2

    def source(self, x, y):
        return ((x-self.offset_x)/self.scale, (y-self.offset_y)/self.scale)

    def screen(self,x,y):
        return (x*self.scale+self.offset_x, y*self.scale+self.offset_y)

    def zoom_at(self, factor, x, y):
        sx,sy=self.source(x,y)
        self.scale = min(8.,max(self.fit_scale*.7,self.scale*factor))
        self.offset_x=x-sx*self.scale
        self.offset_y=y-sy*self.scale
        self._limit()

    def pan(self, dx, dy):
        self.offset_x+=dx; self.offset_y+=dy; self._limit()

    def resize(self, cw, ch):
        sx,sy=self.source(self.canvas_width/2,self.canvas_height/2)
        oldfit=self.fit_scale
        zoom=self.scale/max(oldfit,.001)
        self.canvas_width=max(1,int(cw));self.canvas_height=max(1,int(ch))
        self.fit_scale=min(1.,max(1,self.canvas_width-16)/self.width,
                            max(1,self.canvas_height-16)/self.height)
        self.scale=min(8.,max(self.fit_scale*.7,self.fit_scale*zoom))
        self.offset_x=self.canvas_width/2-sx*self.scale
        self.offset_y=self.canvas_height/2-sy*self.scale
        self._limit()

    def _limit(self):
        # Retain >=32 screen pixels of the image in both axes.
        margin=32
        self.offset_x=min(self.canvas_width-margin,max(margin-self.width*self.scale,self.offset_x))
        self.offset_y=min(self.canvas_height-margin,max(margin-self.height*self.scale,self.offset_y))
