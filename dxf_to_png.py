
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt

def convert_dxf_to_png(dxf_path, png_path):
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Setup matplotlib figure
        fig = plt.figure(figsize=(20, 20))
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        
        # Render
        Frontend(ctx, out).draw_layout(msp, finalize=True)
        
        # Save
        fig.savefig(png_path, dpi=300)
        print(f"Successfully converted {dxf_path} to {png_path}")
        return True
    except Exception as e:
        print(f"Error converting DXF to PNG: {e}")
        return False

if __name__ == "__main__":
    convert_dxf_to_png("Question3_Reinforcement.dxf", "Question3_Reinforcement.png")