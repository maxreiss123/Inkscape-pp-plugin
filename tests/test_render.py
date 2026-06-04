from pplib import render

SVG = "http://www.w3.org/2000/svg"

FLOW = """flowchart LR
  A[Source] --> B[Bridge]
  B -->|plots| C[Tracker]
  B --> D{ok?}
  D -->|yes| E((done))
  D -->|no| F([retry])
"""


def test_parse_flowchart_nodes_and_edges():
    direction, nodes, edges, order = render.parse_flowchart(FLOW)
    assert direction == "LR"
    assert set(nodes) == {"A", "B", "C", "D", "E", "F"}
    assert nodes["A"]["label"] == "Source"
    assert nodes["D"]["shape"] == "rhombus"
    assert nodes["E"]["shape"] == "circle"
    assert nodes["F"]["shape"] == "stadium"
    # B has edges to C (labelled) and D
    assert any(e["src"] == "B" and e["dst"] == "C" and e["label"] == "plots"
               for e in edges)
    assert any(e["src"] == "D" and e["dst"] == "E" and e["label"] == "yes"
               for e in edges)


def test_render_flowchart_produces_shapes_and_text():
    result = render.render_flowchart(FLOW, 1600, 800)
    assert result is not None
    group, cw, ch = result
    texts = group.findall(".//{%s}text" % SVG)
    joined = " ".join("".join(t.itertext()) for t in texts)
    for word in ("Source", "Bridge", "Tracker", "done"):
        assert word in joined
    # Arrow paths exist (edges + arrowheads).
    paths = group.findall(".//{%s}path" % SVG)
    assert len(paths) >= 5
    assert cw > 0 and ch > 0


def test_mermaid_kind_detection():
    assert render._mermaid_kind("flowchart TD\n A-->B") == "flowchart"
    assert render._mermaid_kind("graph LR\n A-->B") == "graph"
    assert render._mermaid_kind("sequenceDiagram\n A->>B: hi") == "sequencediagram"


def test_amp_grouping_creates_multiple_edges():
    _, nodes, edges, _ = render.parse_flowchart("flowchart LR\n A --> B & C")
    pairs = {(e["src"], e["dst"]) for e in edges}
    assert ("A", "B") in pairs and ("A", "C") in pairs


def test_inline_edge_label_form():
    _, _, edges, _ = render.parse_flowchart("flowchart LR\n A -- hello --> B")
    assert any(e["label"] == "hello" for e in edges)
