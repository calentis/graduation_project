# ============================================================
# diagrams_cad.py # DXF/CAD Diagram Generation
# ============================================================
"""
Creates professional DXF drawings for slab reinforcement.
Style based on Turkish structural engineering conventions.

Uses ezdxf library: pip install ezdxf
"""

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment
from typing import Dict, Tuple, List, Optional
from models import DesignOut, BarChoice
from system_solver import SlabSystem, SlabNode

# Drawing Constants
LAYER_OUTLINE = "OUTLINE"
LAYER_BEAM = "BEAM"
LAYER_REBAR_BOT_X = "REBAR_BOT_X"
LAYER_REBAR_BOT_Y = "REBAR_BOT_Y"
LAYER_REBAR_SUP = "REBAR_SUP"
LAYER_DIM = "DIM"
LAYER_LABEL = "LABEL"

COLOR_WHITE = 7
COLOR_GRAY = 8
COLOR_RED = 1
COLOR_GREEN = 3
COLOR_BLUE = 5
COLOR_YELLOW = 2
COLOR_CYAN = 4

BEAM_W_DRAW = 250 # mm default for drawing if not specified

def format_bar_label(c: Optional[BarChoice]) -> str:
    """Format bar as string (e.g., Ø8/17)"""
    if c is None or c.phi <= 0:
        return "-"
    spacing_cm = c.s_cm
    return f"%%C{c.phi}/{spacing_cm:.0f}"

def setup_layers(doc):
    doc.layers.add(LAYER_OUTLINE, color=COLOR_WHITE)
    doc.layers.add(LAYER_BEAM, color=COLOR_GRAY)
    doc.layers.add(LAYER_REBAR_BOT_X, color=COLOR_RED)
    doc.layers.add(LAYER_REBAR_BOT_Y, color=COLOR_GREEN)
    doc.layers.add(LAYER_REBAR_SUP, color=COLOR_BLUE)
    doc.layers.add(LAYER_DIM, color=COLOR_YELLOW)
    doc.layers.add(LAYER_LABEL, color=COLOR_CYAN)

def calculate_layout(system: SlabSystem) -> Dict[str, Tuple[float, float]]:
    """
    Calculate (x, y) origin (bottom-left corner) for each slab in mm.
    Simple BFS layout based on connections.
    """
    if not system.slabs:
        return {}
        
    positions: Dict[str, Tuple[float, float]] = {}
    
    # Start with the first added slab at (0,0)
    first_id = list(system.slabs.keys())[0]
    positions[first_id] = (0.0, 0.0)

    queue = [first_id]
    processed = {first_id}    

    while queue:
        curr_id = queue.pop(0)
        curr_pos = positions[curr_id]
        curr_slab = system.slabs[curr_id]
        
        # Find connections involving this slab
        for conn in system.connections:
            neighbor_id = None
            rel_pos = None # (dx, dy) relative to current origin
            
            # Determine neighbor and relative position
            if conn.slab1_id == curr_id:
                neighbor_id = conn.slab2_id
                
                # Check edges
                # Logic: S1(Right) -> S2(Left) => S2.x = S1.x + S1.Lx + beam
                if conn.edge1 == "right" and conn.edge2 == "left":
                    # S2 is to the right of S1
                    # Align tops (Y-coordinates)?
                    # Usually grids align at top-left. Let's assume top alignment for simplicity in row
                    # Or bottom alignment. Let's try to align such that shared edges overlap.
                    # If S1 Right connects to S2 Left, they share the vertical beam.
                    # So S2.x = S1.x + S1.Lx_mm
                    # S2.y = S1.y (align bottom) ? Or align top?
                    # Let's align bottom-left to bottom-left relative shift.
                    # Shift X = S1.Lx + Beam (if we draw beams separately) or just S1.Lx if shared.
                    # Let's assume center-to-center or face-to-face. 
                    # Let's use face-to-face. 
                    shift_x = curr_slab.data.lx * 1000 + BEAM_W_DRAW
                    shift_y = 0 # Align bottom
                    rel_pos = (shift_x, shift_y)
                    
                elif conn.edge1 == "left" and conn.edge2 == "right":
                    # S2 is to the left of S1
                    shift_x = -(system.slabs[neighbor_id].data.lx * 1000 + BEAM_W_DRAW)
                    shift_y = 0
                    rel_pos = (shift_x, shift_y)
                    
                elif conn.edge1 == "top" and conn.edge2 == "bottom":
                    # S2 is above S1
                    shift_x = 0 # Align left
                    shift_y = curr_slab.data.ly * 1000 + BEAM_W_DRAW
                    rel_pos = (shift_x, shift_y)
                    
                elif conn.edge1 == "bottom" and conn.edge2 == "top":
                    # S2 is below S1
                    shift_x = 0
                    shift_y = -(system.slabs[neighbor_id].data.ly * 1000 + BEAM_W_DRAW)
                    rel_pos = (shift_x, shift_y)
            
            elif conn.slab2_id == curr_id:
                neighbor_id = conn.slab1_id
                # Reverse logic... 
                # If S2(curr) is Left of S1(neigh) => S2(Right) - S1(Left)
                # If conn is S1(Right) -> S2(Left) (This case)
                if conn.edge1 == "right" and conn.edge2 == "left":
                    # S1 is left of S2. 
                    shift_x = -(system.slabs[neighbor_id].data.lx * 1000 + BEAM_W_DRAW)
                    shift_y = 0
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "left" and conn.edge2 == "right":
                    # S1 is right of S2
                    shift_x = curr_slab.data.lx * 1000 + BEAM_W_DRAW
                    shift_y = 0
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "top" and conn.edge2 == "bottom":
                    # S1 is below S2
                    shift_x = 0
                    shift_y = -(system.slabs[neighbor_id].data.ly * 1000 + BEAM_W_DRAW)
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "bottom" and conn.edge2 == "top":
                    # S1 is above S2
                    shift_x = 0
                    shift_y = curr_slab.data.ly * 1000 + BEAM_W_DRAW
                    rel_pos = (shift_x, shift_y)

            if neighbor_id and neighbor_id not in processed and rel_pos:
                positions[neighbor_id] = (curr_pos[0] + rel_pos[0], curr_pos[1] + rel_pos[1])
                processed.add(neighbor_id)
                queue.append(neighbor_id)
                
    return positions

def draw_slab_outline(msp, origin, slab: SlabNode):
    x, y = origin
    w = slab.data.lx * 1000
    h = slab.data.ly * 1000

    # Outer rectangle
    pts = [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)]
    msp.add_lwpolyline(pts, dxfattribs={"layer": LAYER_OUTLINE, "lineweight": 50})

    # Label
    label = f"{slab.id}\nh={slab.data.h_mm:.0f}cm"
    text = msp.add_mtext(label, dxfattribs={"layer": LAYER_LABEL, "char_height": 100})
    text.set_location((x + 200, y + h - 200), attachment_point=1) # Top Left

def draw_straight_bar(msp, start, end, label, layer, hook_len=100):
    """Draws a straight bar with hooks"""
    msp.add_line(start, end, dxfattribs={"layer": layer, "lineweight": 35})

    # Hooks - Assuming 90 deg down/left depending on orientation
    # Determine orientation
    dx = end[0] - start[0]
    dy = end[1] - start[1]

    if abs(dx) > abs(dy): # Horizontal
        # Hooks down
        msp.add_line(start, (start[0], start[1] - hook_len), dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line(end, (end[0], end[1] - hook_len), dxfattribs={"layer": layer, "lineweight": 35})

        # Label
        mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
        msp.add_text(label, dxfattribs={"layer": layer, "height": 60}).set_placement((mid[0], mid[1] + 20), align=TextEntityAlignment.CENTER)
    else: # Vertical
        # Hooks left
        msp.add_line(start, (start[0] - hook_len, start[1]), dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line(end, (end[0] - hook_len, end[1]), dxfattribs={"layer": layer, "lineweight": 35})

        # Label
        mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
        msp.add_text(label, dxfattribs={"layer": layer, "height": 60, "rotation": 90}).set_placement((mid[0] + 20, mid[1]), align=TextEntityAlignment.CENTER)

def draw_pilye_bar(msp, start, end, l_clear, label, layer, hook_len=100):
    """Draws a pilye (bent) bar representation"""
    # Pilye shape: Straight bottom -> crank up -> Straight top -> Hook
    # Standard: Crank starts at L/5 from support (approx)

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = (dx**2 + dy**2)**0.5

    crank_offset = l_clear / 5.0 # Distance from support to bend
    # In this simplified drawing, start/end are beam edges/outer edges.

    if abs(dx) > abs(dy): # Horizontal
        # P1 (Left hook end) -> P2 (Bottom start) -> P3 (Crank up start) -> P4 (Crank up end) ...
        # Simplified plan view: Line with 'crank' symbol or just the line.
        # Let's draw the full line with a specific linetype or just label it "Pilye".
        # Better: Draw the "offset" look.
        # Top parts are at y + offset, Bottom at y.
        
        offset = 0 # In plan, we usually draw them flat but maybe dashed or just solid with a distinct symbol.
        # Let's draw it solid line with 45 deg ticks at bend points.
        
        y = start[1]
        x1 = start[0]
        x2 = end[0]
        
        # Bend points
        b1 = x1 + crank_offset
        b2 = x2 - crank_offset
        
        # Draw main line
        msp.add_line((x1, y), (x2, y), dxfattribs={"layer": layer, "lineweight": 35})
        
        # Draw ticks at bends (visual cue)
        tick_h = 50
        msp.add_line((b1-tick_h, y-tick_h), (b1+tick_h, y+tick_h), dxfattribs={"layer": layer})
        msp.add_line((b2-tick_h, y-tick_h), (b2+tick_h, y+tick_h), dxfattribs={"layer": layer})
        
        # Hooks (down)
        msp.add_line((x1, y), (x1, y - hook_len), dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line((x2, y), (x2, y - hook_len), dxfattribs={"layer": layer, "lineweight": 35})
        
        # Label
        mid = ((x1+x2)/2, y)
        msp.add_text(label + " (Pilye)", dxfattribs={"layer": layer, "height": 60}).set_placement((mid[0], mid[1] + 20), align=TextEntityAlignment.CENTER)

    else: # Vertical
        x = start[0]
        y1 = start[1]
        y2 = end[1]
        
        b1 = y1 + crank_offset
        b2 = y2 - crank_offset
        
        msp.add_line((x, y1), (x, y2), dxfattribs={"layer": layer, "lineweight": 35})
        
        tick_w = 50
        msp.add_line((x-tick_w, b1-tick_w), (x+tick_w, b1+tick_w), dxfattribs={"layer": layer})
        msp.add_line((x-tick_w, b2-tick_w), (x+tick_w, b2+tick_w), dxfattribs={"layer": layer})
        
        # Hooks (left)
        msp.add_line((x, y1), (x - hook_len, y1), dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line((x, y2), (x - hook_len, y2), dxfattribs={"layer": layer, "lineweight": 35})
        
        # Label
        mid = (x, (y1+y2)/2)
        msp.add_text(label + " (Pilye)", dxfattribs={"layer": layer, "height": 60, "rotation": 90}).set_placement((mid[0] + 20, mid[1]), align=TextEntityAlignment.CENTER)

def draw_support_bar(msp, edge_center, label, orientation="H"):
    """Draws additional top bar (Ek) over support"""
    # Length usually l/4 of adjacent spans. Let's use fixed length for diagram.
    L_bar = 1500 # mm

    if orientation == "H":
        start = (edge_center[0] - L_bar/2, edge_center[1])
        end = (edge_center[0] + L_bar/2, edge_center[1])
        msp.add_line(start, end, dxfattribs={"layer": LAYER_REBAR_SUP, "lineweight": 40})
        # Hooks down
        msp.add_line(start, (start[0], start[1]-50), dxfattribs={"layer": LAYER_REBAR_SUP})
        msp.add_line(end, (end[0], end[1]-50), dxfattribs={"layer": LAYER_REBAR_SUP})
        
        msp.add_text(label + " (Ek)", dxfattribs={"layer": LAYER_REBAR_SUP, "height": 60}).set_placement((edge_center[0], edge_center[1] + 30), align=TextEntityAlignment.CENTER)
    else:
        start = (edge_center[0], edge_center[1] - L_bar/2)
        end = (edge_center[0], edge_center[1] + L_bar/2)
        msp.add_line(start, end, dxfattribs={"layer": LAYER_REBAR_SUP, "lineweight": 40})
        # Hooks left
        msp.add_line(start, (start[0]-50, start[1]), dxfattribs={"layer": LAYER_REBAR_SUP})
        msp.add_line(end, (end[0]-50, end[1]), dxfattribs={"layer": LAYER_REBAR_SUP})
        
        msp.add_text(label + " (Ek)", dxfattribs={"layer": LAYER_REBAR_SUP, "height": 60, "rotation": 90}).set_placement((edge_center[0] + 30, edge_center[1]), align=TextEntityAlignment.CENTER)


def generate_system_dxf(system: SlabSystem, output_file: str = "system_reinforcement.dxf"):
    doc = ezdxf.new("R2010")
    doc.units = units.MM
    setup_layers(doc)
    msp = doc.modelspace()

    # 1. Layout Slabs
    positions = calculate_layout(system)

    # 2. Draw Slabs and Rebars
    for slab_id, origin in positions.items():
        slab = system.slabs[slab_id]
        draw_slab_outline(msp, origin, slab)
        
        x0, y0 = origin
        w = slab.data.lx * 1000
        h = slab.data.ly * 1000
        
        # --- Bottom Rebar X ---
        if slab.design_x:
            # Layout: Straight at ~1/4 height, Pilye at ~3/4 height within the slab plan?
            # Or usually distributed. Let's draw one representative straight and one pilye if they exist.
            
            # Straight
            if slab.design_x.main_bottom_layout and slab.design_x.main_bottom_layout.straight.phi > 0:
                bar = slab.design_x.main_bottom_layout.straight
                lbl = format_bar_label(bar)
                y_pos = y0 + h * 0.25
                draw_straight_bar(msp, (x0 + 50, y_pos), (x0 + w - 50, y_pos), lbl, LAYER_REBAR_BOT_X)
                
            # Pilye
            if slab.design_x.main_bottom_layout and slab.design_x.main_bottom_layout.pilye.phi > 0:
                bar = slab.design_x.main_bottom_layout.pilye
                lbl = format_bar_label(bar)
                y_pos = y0 + h * 0.4
                draw_pilye_bar(msp, (x0, y_pos), (x0 + w, y_pos), w, lbl, LAYER_REBAR_BOT_X)
            
            # Distribution (if one-way)
            if slab.design_x.dist_bars and slab.design_x.dist_bars.phi > 0:
                 # Draw simplified straight bar
                 bar = slab.design_x.dist_bars
                 lbl = "Dag: " + format_bar_label(bar)
                 y_pos = y0 + h * 0.5
                 draw_straight_bar(msp, (x0 + 50, y_pos), (x0 + w - 50, y_pos), lbl, LAYER_REBAR_BOT_X)

        # --- Bottom Rebar Y ---
        if slab.design_y:
            # Straight
            if slab.design_y.main_bottom_layout and slab.design_y.main_bottom_layout.straight.phi > 0:
                bar = slab.design_y.main_bottom_layout.straight
                lbl = format_bar_label(bar)
                x_pos = x0 + w * 0.25
                draw_straight_bar(msp, (x_pos, y0 + 50), (x_pos, y0 + h - 50), lbl, LAYER_REBAR_BOT_Y)
            
            # Pilye
            if slab.design_y.main_bottom_layout and slab.design_y.main_bottom_layout.pilye.phi > 0:
                bar = slab.design_y.main_bottom_layout.pilye
                lbl = format_bar_label(bar)
                x_pos = x0 + w * 0.4
                draw_pilye_bar(msp, (x_pos, y0), (x_pos, y0 + h), h, lbl, LAYER_REBAR_BOT_Y)
                
            # Distribution
            if slab.design_y.dist_bars and slab.design_y.dist_bars.phi > 0:
                 bar = slab.design_y.dist_bars
                 lbl = "Dag: " + format_bar_label(bar)
                 x_pos = x0 + w * 0.5
                 draw_straight_bar(msp, (x_pos, y0 + 50), (x_pos, y0 + h - 50), lbl, LAYER_REBAR_BOT_Y)

        # --- Support Bars (Additional Top) ---
        for edge, bar in slab.support_reinforcement.items():
            if bar.phi <= 0: continue
            lbl = format_bar_label(bar)
            
            if edge == "right":
                center = (x0 + w, y0 + h/2)
                draw_support_bar(msp, center, lbl, "H")
            elif edge == "left":
                center = (x0, y0 + h/2)
                draw_support_bar(msp, center, lbl, "H")
            elif edge == "top":
                center = (x0 + w/2, y0 + h)
                draw_support_bar(msp, center, lbl, "V")
            elif edge == "bottom":
                center = (x0 + w/2, y0)
                draw_support_bar(msp, center, lbl, "V")

    # 3. Save
    doc.saveas(output_file)
    print(f"DXF created: {output_file}")
    return output_file