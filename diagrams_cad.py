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
    """Format bar as string (e.g., %%C8/17)"""
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
    first_id = list(system.slabs.keys())[0]
    positions[first_id] = (0.0, 0.0)

    queue = [first_id]
    processed = {first_id}

    while queue:
        curr_id = queue.pop(0)
        curr_pos = positions[curr_id]
        curr_slab = system.slabs[curr_id]
        
        for conn in system.connections:
            neighbor_id = None
            rel_pos = None 
            
            if conn.slab1_id == curr_id:
                neighbor_id = conn.slab2_id
                if conn.edge1 == "right" and conn.edge2 == "left":
                    shift_x = curr_slab.data.lx * 1000 + BEAM_W_DRAW
                    shift_y = 0
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "left" and conn.edge2 == "right":
                    shift_x = -(system.slabs[neighbor_id].data.lx * 1000 + BEAM_W_DRAW)
                    shift_y = 0
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "top" and conn.edge2 == "bottom":
                    shift_x = 0
                    shift_y = curr_slab.data.ly * 1000 + BEAM_W_DRAW
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "bottom" and conn.edge2 == "top":
                    shift_x = 0
                    shift_y = -(system.slabs[neighbor_id].data.ly * 1000 + BEAM_W_DRAW)
                    rel_pos = (shift_x, shift_y)
            
            elif conn.slab2_id == curr_id:
                neighbor_id = conn.slab1_id
                if conn.edge1 == "right" and conn.edge2 == "left":
                    shift_x = -(system.slabs[neighbor_id].data.lx * 1000 + BEAM_W_DRAW)
                    shift_y = 0
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "left" and conn.edge2 == "right":
                    shift_x = curr_slab.data.lx * 1000 + BEAM_W_DRAW
                    shift_y = 0
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "top" and conn.edge2 == "bottom":
                    shift_x = 0
                    shift_y = -(system.slabs[neighbor_id].data.ly * 1000 + BEAM_W_DRAW)
                    rel_pos = (shift_x, shift_y)
                elif conn.edge1 == "bottom" and conn.edge2 == "top":
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
    text.set_location((x + 200, y + h - 200), attachment_point=1)

def draw_hook(msp, pt, direction, layer, hook_len=100):
    """Draw a 90 degree hook at pt in 'direction' ((dx, dy) vector)"""
    end = (pt[0] + direction[0] * hook_len, pt[1] + direction[1] * hook_len)
    msp.add_line(pt, end, dxfattribs={"layer": layer, "lineweight": 35})

def draw_straight_bar(msp, start, end, label, layer, hook_len=100):
    """Draws a straight bar with hooks at ends (turned in)"""
    msp.add_line(start, end, dxfattribs={"layer": layer, "lineweight": 35})

    # Determine orientation
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    
    if abs(dx) > abs(dy): # Horizontal
        # Hooks turn UP or DOWN? Standard plan view: hooks turn inwards or towards beam core.
        # Often drawn 'in plan' as a C shape.
        # Let's draw hooks pointing UP for horizontal bars (arbitrary convention)
        # unless it creates clutter. User image has vertical bars with hooks pointing Left/Right.
        # Let's make hooks point 'inwards' to the slab center to look like a containment.
        
        # Hooks at start (Left) -> Point Right? No, hooks are vertical legs.
        # In plan view, a hook is a line perpendicular to the bar.
        # Let's draw hooks pointing 'Down' for horizontal bars.
        draw_hook(msp, start, (0, -1), layer, hook_len)
        draw_hook(msp, end, (0, -1), layer, hook_len)
        
        # Label
        mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
        msp.add_text(label, dxfattribs={"layer": layer, "height": 60}).set_placement((mid[0], mid[1] + 20), align=TextEntityAlignment.CENTER)
    else: # Vertical
        # Hooks turn Left
        draw_hook(msp, start, (-1, 0), layer, hook_len)
        draw_hook(msp, end, (-1, 0), layer, hook_len)
        
        # Label
        mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
        msp.add_text(label, dxfattribs={"layer": layer, "height": 60, "rotation": 90}).set_placement((mid[0] + 20, mid[1]), align=TextEntityAlignment.CENTER)

def draw_pilye_bar(msp, start, end, l_clear, label, layer, hook_len=100, extend_start=0, extend_end=0):
    """
    Draws a Pilye (Cranked) bar.
    Representation: 
    Support(Top) --crank-- Span(Bottom) --crank-- Support(Top)
    Visual: Line with offsets/jogs at L/5 points.

    extend_start: Length to extend past the start point (Top level)
    extend_end: Length to extend past the end point (Top level)
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    
    crank_dist = l_clear / 5.0
    crank_width = 150 # Visual width of the jog

    if abs(dx) > abs(dy): # Horizontal
        x1, y = start
        x2, _ = end
        
        # p1 (start) -- p2 (crank start)
        # If extending, start point moves Left (x1 - extend_start)
        p1 = (x1 - extend_start, y)
        p2 = (x1 + crank_dist, y)
        
        # p3 (crank bottom start) -- p4 (crank bottom end)
        p3 = (x1 + crank_dist + crank_width, y - crank_width)
        p4 = (x2 - crank_dist - crank_width, y - crank_width)
        
        # p5 (crank up end) -- p6 (end)
        # If extending, end point moves Right (x2 + extend_end)
        p5 = (x2 - crank_dist, y)
        p6 = (x2 + extend_end, y)
        
        # Draw segments
        msp.add_line(p1, p2, dxfattribs={"layer": layer, "lineweight": 35}) # Top Left
        msp.add_line(p2, p3, dxfattribs={"layer": layer, "lineweight": 35}) # Crank Down
        msp.add_line(p3, p4, dxfattribs={"layer": layer, "lineweight": 35}) # Bottom Span
        msp.add_line(p4, p5, dxfattribs={"layer": layer, "lineweight": 35}) # Crank Up
        msp.add_line(p5, p6, dxfattribs={"layer": layer, "lineweight": 35}) # Top Right
        
        # Hooks (Down from Top level)
        draw_hook(msp, p1, (0, -1), layer, hook_len)
        draw_hook(msp, p6, (0, -1), layer, hook_len)
        
        # Label
        mid_x = (p3[0] + p4[0]) / 2
        mid_y = p3[1]
        msp.add_text(label + " (Pilye)", dxfattribs={"layer": layer, "height": 60}).set_placement((mid_x, mid_y + 20), align=TextEntityAlignment.CENTER)

    else: # Vertical
        x, y1 = start
        _, y2 = end
        
        # Points
        # Start moves Down (y1 - extend_start)
        p1 = (x, y1 - extend_start)
        p2 = (x, y1 + crank_dist)
        
        # Jog Right
        p3 = (x + crank_width, y1 + crank_dist + crank_width)
        p4 = (x + crank_width, y2 - crank_dist - crank_width)
        
        p5 = (x, y2 - crank_dist)
        # End moves Up (y2 + extend_end)
        p6 = (x, y2 + extend_end)
        
        msp.add_line(p1, p2, dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line(p2, p3, dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line(p3, p4, dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line(p4, p5, dxfattribs={"layer": layer, "lineweight": 35})
        msp.add_line(p5, p6, dxfattribs={"layer": layer, "lineweight": 35})
        
        # Hooks (Left)
        draw_hook(msp, p1, (-1, 0), layer, hook_len)
        draw_hook(msp, p6, (-1, 0), layer, hook_len)
        
        # Label
        mid_x = p3[0]
        mid_y = (p3[1] + p4[1]) / 2
        msp.add_text(label + " (Pilye)", dxfattribs={"layer": layer, "height": 60, "rotation": 90}).set_placement((mid_x - 20, mid_y), align=TextEntityAlignment.CENTER)

def draw_support_bar(msp, edge_center, label, orientation="H"):
    """Draws additional top bar (Ek) over support"""
    L_bar = 1500 # mm

    if orientation == "H":
        start = (edge_center[0] - L_bar/2, edge_center[1])
        end = (edge_center[0] + L_bar/2, edge_center[1])
        msp.add_line(start, end, dxfattribs={"layer": LAYER_REBAR_SUP, "lineweight": 40})
        # Hooks down
        draw_hook(msp, start, (0, -1), LAYER_REBAR_SUP, 50)
        draw_hook(msp, end, (0, -1), LAYER_REBAR_SUP, 50)
        
        msp.add_text(label + " (Ek)", dxfattribs={"layer": LAYER_REBAR_SUP, "height": 60}).set_placement((edge_center[0], edge_center[1] + 30), align=TextEntityAlignment.CENTER)
    else:
        start = (edge_center[0], edge_center[1] - L_bar/2)
        end = (edge_center[0], edge_center[1] + L_bar/2)
        msp.add_line(start, end, dxfattribs={"layer": LAYER_REBAR_SUP, "lineweight": 40})
        # Hooks left
        draw_hook(msp, start, (-1, 0), LAYER_REBAR_SUP, 50)
        draw_hook(msp, end, (-1, 0), LAYER_REBAR_SUP, 50)
        
        msp.add_text(label + " (Ek)", dxfattribs={"layer": LAYER_REBAR_SUP, "height": 60, "rotation": 90}).set_placement((edge_center[0] + 30, edge_center[1]), align=TextEntityAlignment.CENTER)


def get_neighbor_span(system: SlabSystem, slab_id: str, edge: str) -> float:
    """
    Find connected slab and return its span in the connection direction.
    """
    for conn in system.connections:
        neighbor = None
        
        if conn.slab1_id == slab_id and conn.edge1 == edge:
            neighbor = system.slabs[conn.slab2_id]
        elif conn.slab2_id == slab_id and conn.edge2 == edge:
            neighbor = system.slabs[conn.slab1_id]
            
        if neighbor:
            # If connected Left/Right -> Continuity along X -> Need X span
            if edge in ["left", "right"]:
                # Check for cantilever
                if neighbor.data.slab_case == 8:
                    # For cantilever, extend full length
                    return neighbor.data.lx * 1000
                return neighbor.data.lx * 1000 / 4
            # If connected Top/Bottom -> Continuity along Y -> Need Y span
            elif edge in ["top", "bottom"]:
                if neighbor.data.slab_case == 8:
                    return neighbor.data.ly * 1000
                return neighbor.data.ly * 1000 / 4
                
    return 0.0

def generate_system_dxf(system: SlabSystem, output_file: str = "system_reinforcement.dxf"):
    doc = ezdxf.new("R2010")
    doc.units = units.MM
    setup_layers(doc)
    msp = doc.modelspace()

    positions = calculate_layout(system)

    for slab_id, origin in positions.items():
        slab = system.slabs[slab_id]
        draw_slab_outline(msp, origin, slab)
        
        x0, y0 = origin
        w = slab.data.lx * 1000
        h = slab.data.ly * 1000
        
        # Use offset spacing to prevent overlap
        # Center of slab
        cx = x0 + w/2
        cy = y0 + h/2
        
        # Determine extensions
        ext_left = get_neighbor_span(system, slab_id, "left")
        ext_right = get_neighbor_span(system, slab_id, "right")
        ext_top = get_neighbor_span(system, slab_id, "top")
        ext_bottom = get_neighbor_span(system, slab_id, "bottom")
        
        # --- Bottom Rebar X (Horizontal) ---
        if slab.design_x:
            # Draw Straight at Y center
            if slab.design_x.main_bottom_layout and slab.design_x.main_bottom_layout.straight.phi > 0:
                bar = slab.design_x.main_bottom_layout.straight
                lbl = format_bar_label(bar)
                # Offset straight slightly up
                y_pos = cy + 100
                draw_straight_bar(msp, (x0 + 50, y_pos), (x0 + w - 50, y_pos), lbl, LAYER_REBAR_BOT_X)
                
            # Draw Pilye at Y center (Offset down)
            if slab.design_x.main_bottom_layout and slab.design_x.main_bottom_layout.pilye.phi > 0:
                bar = slab.design_x.main_bottom_layout.pilye
                lbl = format_bar_label(bar)
                y_pos = cy - 100
                draw_pilye_bar(msp, (x0, y_pos), (x0 + w, y_pos), w, lbl, LAYER_REBAR_BOT_X, 
                               extend_start=ext_left, extend_end=ext_right)
            
            # Distribution (One way)
            if slab.design_x.dist_bars and slab.design_x.dist_bars.phi > 0:
                 bar = slab.design_x.dist_bars
                 lbl = "Dag: " + format_bar_label(bar)
                 draw_straight_bar(msp, (x0 + 50, cy), (x0 + w - 50, cy), lbl, LAYER_REBAR_BOT_X)

        # --- Bottom Rebar Y (Vertical) ---
        if slab.design_y:
            # Straight at X center (Offset Left)
            if slab.design_y.main_bottom_layout and slab.design_y.main_bottom_layout.straight.phi > 0:
                bar = slab.design_y.main_bottom_layout.straight
                lbl = format_bar_label(bar)
                x_pos = cx - 100
                draw_straight_bar(msp, (x_pos, y0 + 50), (x_pos, y0 + h - 50), lbl, LAYER_REBAR_BOT_Y)
            
            # Pilye at X center (Offset Right)
            if slab.design_y.main_bottom_layout and slab.design_y.main_bottom_layout.pilye.phi > 0:
                bar = slab.design_y.main_bottom_layout.pilye
                lbl = format_bar_label(bar)
                x_pos = cx + 100
                draw_pilye_bar(msp, (x_pos, y0), (x_pos, y0 + h), h, lbl, LAYER_REBAR_BOT_Y,
                               extend_start=ext_bottom, extend_end=ext_top)
                
            # Distribution
            if slab.design_y.dist_bars and slab.design_y.dist_bars.phi > 0:
                 bar = slab.design_y.dist_bars
                 lbl = "Dag: " + format_bar_label(bar)
                 draw_straight_bar(msp, (cx, y0 + 50), (cx, y0 + h - 50), lbl, LAYER_REBAR_BOT_Y)

        # --- Support Bars (Additional Top) ---
        for edge, bar in slab.support_reinforcement.items():
            if bar.phi <= 0: continue
            lbl = format_bar_label(bar)
            
            if edge == "right":
                draw_support_bar(msp, (x0 + w, cy), lbl, "H")
            elif edge == "left":
                draw_support_bar(msp, (x0, cy), lbl, "H")
            elif edge == "top":
                draw_support_bar(msp, (cx, y0 + h), lbl, "V")
            elif edge == "bottom":
                draw_support_bar(msp, (cx, y0), lbl, "V")

    doc.saveas(output_file)
    print(f"DXF created: {output_file}")
    return output_file