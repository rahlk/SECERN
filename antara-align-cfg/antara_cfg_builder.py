import os
import sys
import shlex
import subprocess
import pandas as pd
import networkx as nx
from tqdm import tqdm
from pathlib import Path
from pdb import set_trace
import matplotlib.pyplot as plt

# Add project source to path
root = Path(os.path.abspath(os.path.join(
    os.getcwd().split('antara')[0], 'antara')))

py_path = root.joinpath('antara-align-cfg')
if py_path not in sys.path:
    sys.path.append(py_path)

class CFGBuilder:
    def __init__(self, binary_path, test_input_path, project_name=""):
        """ Build a dynamic call graph.
        
        Parameters
        ----------
        binary_path: str (or pathlib.PosixPath)
            Path to the binary
        test_input_path: str (or pathlib.PosixPath)
            Directory containing the test_inputs 
        """
        self.binary_path = binary_path
        self.test_input_path = test_input_path
        self.prj_name = project_name
    
    def __enter__(self):
        """ Context manager initialization.
        """
        return self

    @staticmethod
    def draw_call_graph(G, fname="tmp.pdf"):
        """ Convert callgraph to a pdf

        Parameters
        ----------
        G: nx.DiGraph
            Input graph
        fname: str
            File name to save as
        """
        nx.drawing.nx_pydot.write_dot(G, fname)

    @staticmethod
    def _calltrace_to_callgraph(trace_df):
        """ Convert call trace to the callgraph

        Parameters
        ----------
        trace_df: pandas.DataFrame
            The call trace over several runs a dataframe 
        
        Returns
        -------
        nx.DiGraph
            Call graph
        """

        # Aggregate the run callgraph edge counts
        grouped = trace_df.groupby(trace_df.columns.tolist()).size().reset_index().rename(columns={0: 'label'})

        # Initialize and populate weighted-directed-graph 
        Graphtype = nx.DiGraph()
        G = nx.from_pandas_edgelist(grouped, edge_attr=True, create_using=Graphtype)
        return G

    @staticmethod
    def graph_to_adjacency_matrix(G, use_weights=True):
        """ Convert a networkx graph to an adjacency matrix

        Parameters
        ----------
        G: nx.DiGraph
            Input networkx graph
        use_weights: bool
            Include weights to populate the adjacency matrix values

        Returns
        -------
        scipy.sparse
            A sparse adjacency matrix
        """
        node_list = tuple(G.nodes())
        if use_weights:
            adj_mtx = nx.linalg.graphmatrix.adjacency_matrix(G, weight='label')
        else:
            adj_mtx = nx.linalg.graphmatrix.adjacency_matrix(G, weight=None)

        return node_list, adj_mtx

    def get_dynamic_call_graph(self, opt_flags="", seed_id=0):
        """ Runs a test input on the instrumented program to gather the dynamic 
            call graph.

        Parameters
        ----------
        opt_flags: str 
            Commandline arguments/flag
        test_input_path: str (or pathlib.PosixPath)
            Directory containing the test_inputs 
        
        Returns
        -------
        nx.DiGraph
            A networkx style directed weighted call graph.
        
        Notes
        -----
          - The edge weights represent the number of times the <caller, callee> 
            pair has been invoked.
        """
        binary_path = self.binary_path
        test_input_path = self.test_input_path
        
        if isinstance(binary_path, str):
            binary_path = Path(binary_path)
        
        if isinstance(test_input_path, str):
            test_input_path = Path(test_input_path)
        
        assert binary_path.exists(), "Binary path does not exist."
        assert test_input_path.exists(), "Test inputs path does not exist."

        call_trace_df = pd.DataFrame(columns=['source', 'target'])

        # Loop through the test files and run them on the binary. 
        for input_num, test_input in enumerate(test_input_path.glob("*")):
            if input_num != seed_id:
                continue
            else:
                # Run the instrumented binary
                subprocess.run([binary_path, opt_flags, test_input],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Convert the raw calltrace to a pandas dataframe
                call_trace = pd.read_csv('callgraph.csv')
                call_trace_df = call_trace_df.append(call_trace)
                    
        
        # Convert the calltrace to a NetworkX graph
        G = self._calltrace_to_callgraph(call_trace_df)

        return G

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Clean up opertaions
        """
        pwd = os.getcwd()
        files_to_clean_up = ['callgraph.csv', 'callgraph.dot', 'out_data.dot', 'outfile.pdf', 'plotgraph.png']
        for f in map(Path, files_to_clean_up):
            if f.exists():
                os.remove(f)
            else:
                continue
