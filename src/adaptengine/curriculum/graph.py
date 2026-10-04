import networkx as nx
from ..core.schema import Concept
from ..core.errors import CycleError


class CurriculumGraph:
    def __init__(self, concepts: tuple[Concept, ...]):
        self._graph = nx.DiGraph()

        for c in concepts:
            self._graph.add_node(c.concept_id)

        for c in concepts:
            for p in c.prerequisites:
                self._graph.add_edge(p, c.concept_id)

        try:
            cycle = nx.find_cycle(self._graph, orientation="original")
            raise CycleError(f"Cycle detected: {cycle}")
        except nx.NetworkXNoCycle:
            pass

    @classmethod
    def from_concepts(cls, concepts: tuple[Concept, ...]) -> "CurriculumGraph":
        return cls(concepts)

    def concepts(self) -> tuple[str, ...]:
        return tuple(sorted(self._graph.nodes()))

    def roots(self) -> tuple[str, ...]:
        return tuple(sorted(n for n, d in self._graph.in_degree() if d == 0))

    def prerequisites(self, c: str) -> tuple[str, ...]:
        return tuple(sorted(self._graph.predecessors(c)))

    def ancestors(self, c: str) -> frozenset[str]:
        return frozenset(nx.ancestors(self._graph, c))

    def descendants(self, c: str) -> frozenset[str]:
        return frozenset(nx.descendants(self._graph, c))

    def descendant_count(self, c: str) -> int:
        return len(self.descendants(c))

    def depth(self, c: str) -> int:
        depths = {}
        for node in nx.lexicographical_topological_sort(self._graph):
            preds = list(self._graph.predecessors(node))
            if not preds:
                depths[node] = 0
            else:
                depths[node] = max(depths[p] for p in preds) + 1
        return depths[c]

    def topological_order(self) -> tuple[str, ...]:
        return tuple(nx.lexicographical_topological_sort(self._graph))
