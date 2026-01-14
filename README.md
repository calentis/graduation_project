# TS500 Slab System Designer

A professional Python-based structural engineering tool for designing reinforced concrete slab systems according to **TS500 (2000)** and **TBDY (2018)** standards.

## Features

*   **Multi-Slab System Solver:** Handles complex layouts with multiple adjacent slabs.
*   **Automatic Moment Balancing:** Calculates moments using coefficient methods and balances them at supports (distributes difference if < 20%, takes max if > 20% or cantilever).
*   **Support for Cantilevers (Balkon):** Correctly handles balcony static moments and their effect on adjacent slabs.
*   **Reinforcement Selection:** Automatically selects:
    *   **Straight Bars (Düz Donatı)**
    *   **Bent Bars (Pilye Donatı)**
    *   **Additional Top Bars (Ek Donatı)** at supports.
*   **DXF Drawing Generation:** Exports professional CAD drawings (`.dxf`) compatible with AutoCAD, BricsCAD, etc.

## Installation

1.  Clone this repository.
2.  Install the required dependencies:
```bash
pip install ezdxf
```

## How to Use

The system uses a programmatic approach to define slab layouts. You create a python script (e.g., `solve_my_project.py`) to define your geometry.

### 1. Define Slabs and Connections

Create a new file (e.g., `project.py`) and use the `SlabSystem` class:

```python
from system_solver import SlabSystem
from models import InputData
from diagrams_cad import generate_system_dxf

def solve():
    # Initialize
    system = SlabSystem()
    
    # Define Materials & Loads
    h = 140.0; cover = 20.0
    conc = "C25"; steel = "S420"
    g = 1.5; q = 3.5
    bw = 250.0

    # Add Slabs (D1, D2, Balcony...)
    # Case 1-7: Standard Slabs, Case 8: Cantilever
    d1 = InputData(lx=6.0, ly=6.0, slab_case=3, slab_id="D1", ...)
    system.add_slab("D1", d1)
    
    d2 = InputData(lx=6.0, ly=6.0, slab_case=3, slab_id="D2", ...)
    system.add_slab("D2", d2)

    # Define Connections (Topology)
    # "D1's Right edge connects to D2's Left edge"
    system.connect("D1", "right", "D2", "left")

    # Solve
    system.solve()
    
    # Generate Drawing
    generate_system_dxf(system, "Project_Output.dxf")

if __name__ == "__main__":
    solve()
```

### 2. Run the Solver

```bash
python3 project.py
```

### 3. View Results

*   **Console Output:** Detailed text report of moments ($M_d$), required area ($A_s$), and selected bars.
*   **DXF File:** Open the generated `.dxf` file in any CAD software to view the reinforcement plan.

## Project Structure

*   `main.py`: Legacy single-slab interactive tool.
*   `system_solver.py`: Core engine for multi-slab systems. Handles balancing and continuity.
*   `models.py`: Data structures for inputs and results.
*   `design.py`: TS500 coefficient method implementation.
*   `core.py`: Reinforcement calculation logic ($K$, $k_s$, $A_s$).
*   `diagrams_cad.py`: DXF generation engine.
*   `solve_question_3.py`: Example solution for a 2-slab + 2-balcony system.

## Supported Slab Cases (TS500)

| Case | Description |
| :--- | :--- |
| 1 | All edges continuous |
| 2 | One short edge discontinuous |
| 3 | Two adjacent edges discontinuous (Corner) |
| 4 | Two short edges discontinuous |
| 5 | Two long edges discontinuous |
| 6 | Three edges discontinuous |
| 7 | Four edges discontinuous (Simple) |
| 8 | **Cantilever (Balkon)** |

## License

MIT License