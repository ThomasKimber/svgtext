from textlayout import word_wrap
from tpipe import phtml
import networkx as nx
from networkx import MultiDiGraph


def html_to_markup(source : str, 
                   word_wrap_limit : int)->list[list[tuple[str,dict[str,dict]]]]:
    """Process a section of text, breaking it into 
    separate lines based on a number of 
    characters defined as a word_wrap_limit and return
    a proprietary markup consisting of lines of text
    broken down into individually styled cells.
    Text can be supplied as straight text, or provided as html
    """
    tgraph=html_text_to_graph(source)
    return [[(text,_get_text_feature_from_graph_hierarchy(tgraph, node)) for text, node in row ] for row in _html_text_word_wrap(source, tgraph, word_wrap_limit) ]



def _html_section_to_text_layout_grid(html_graph, start_node):
    """Given an html structural graph (conforming to the definition 
    in phtml) and a starting node, traverse the graph and extract
    text nodes, placing them into a grid based on linebreaks and
    reading sequence. This grid can then be used to further refine
    layout."""
    linenumber=-1
    last_linenumber=0
    block_sequence=-1
    subtree=phtml.walk_subtree(html_graph,start_node)
    node_line_assignments=[]
    node_line=[]
    node_rows=[]
    for n in subtree:
        node_content = phtml.get_node_data(html_graph, n)
        node_parent_id = phtml.get_parent_node_id(html_graph, n)
        if node_content.tag in ('p', 'br'):
            linenumber=linenumber+1
        if node_content.text is not None and node_content.node_type=='text':
            block_sequence=block_sequence+1
            node_line.append(n)
        if linenumber != last_linenumber and len(node_line)>0:
            block_sequence=-1
            node_rows.append(node_line)
            node_line=[]
        node_line_assignments.append((n, (block_sequence, linenumber)))
        
        last_linenumber=linenumber
    if len(node_line)>0:
        node_rows.append(node_line)
    return node_rows

def range_mapping(t_range, labelled_range_dict):
    mappings=[]
    for k,v in labelled_range_dict.items():
        if ranges_overlap(range(*t_range), range(*v)):
            mappings.append(k)
    return mappings

def ranges_overlap(r1, r2):
    return max(r1.start, r2.start) < min(r1.stop, r2.stop)

def ranges_intersection(r1, r2):
    r_intersect = set(r1).intersection(set(r2))
    return range(min(r_intersect), max(r_intersect))

def range_to_start_end_tuple(r):
    return r.start, r.stop+1

def html_text_to_graph(source: str) -> nx.MultiDiGraph:
    return phtml.html_to_graph(source)

def _html_text_word_wrap(source : str, 
                        tgraph : MultiDiGraph,
                        word_wrap_length : int):
    
    root_el=phtml.root_node_id(tgraph)
    node_line_assignments = _html_section_to_text_layout_grid(tgraph, root_el)
    
    row_node_extents=[]
    for row in node_line_assignments:
        node_extents={}
        row_len=0
        for node in row:
            n_text = phtml.get_node_data(tgraph, node).text
            node_extents[node]=(row_len, row_len+len(n_text))
            row_len=row_len+len(n_text)
        row_node_extents.append(node_extents)
    
    layout_text = ["".join([phtml.get_node_data(tgraph, t).text for t in row_nodes]) for row_nodes in node_line_assignments]
    line_wws=[]
    for line in layout_text:
        wraps=word_wrap(line, word_wrap_length, " .,\n")
        line_wws.append(wraps)

    layout=[r for l in [
            [
                [
                    (e, m,range_to_start_end_tuple(ranges_intersection(range(*row_node_extents[e][m]),range(*c))))
                        for m in (range_mapping(c, row_node_extents[e]))
                ] 
                    for c in r
            ] 
                for e,r in enumerate(line_wws)
            ]
            for r in l]
    
    return [[(layout_text[node_span[0]][slice(*node_span[2])], node_span[1]) 
      for node_span in span] 
         for span in layout]


def _get_text_feature_from_graph_hierarchy(graph, node):
    features={}
    ancestors = [a for a in phtml.get_ancestors(graph, node)]
    tag_name_mapping={
        "a" : "link",
        "b" : "bold",
        "i" : "italic",
        "sup" : "super",
        "sub" : "sub"
    }

    tag__attribute_mapping={
        "a" : {"href", "title", "target"},
        "b" : {},
        "i" : {},
        "sup" : {},
        "sub" : {}
    }

    for a in ancestors:
        a_node = graph.nodes(data=True)[a]
        attribute_map = tag__attribute_mapping.get(a_node['data'].tag, None)
        if attribute_map is not None :
            features={**features, **{tag_name_mapping.get(a_node['data'].tag) : {v:a_node['data'].attributes.get(v) for v in attribute_map}}}
    return features
