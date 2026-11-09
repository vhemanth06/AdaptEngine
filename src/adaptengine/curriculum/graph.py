import networkx as nx
from ..core.schema import Concept
from ..core.errors import CycleError, UnknownConceptError


class CurriculumGraph:
    def __init__(self, concepts: tuple[Concept, ...]):
        self._graph = nx.DiGraph()

        known_concepts = {c.concept_id for c in concepts}
        for c in concepts:
            self._graph.add_node(c.concept_id)

        for c in concepts:
            for p in c.prerequisites:
                if p not in known_concepts:
                    raise UnknownConceptError(
                        f"Concept {c.concept_id} references unknown prerequisite {p}"
                    )
                self._graph.add_edge(p, c.concept_id)

        try:
            cycle = nx.find_cycle(self._graph, orientation="original")
            raise CycleError(f"Cycle detected: {cycle}")
        except nx.NetworkXNoCycle:
            pass

        # T6.1: the graph is immutable, so every query the planner's inner loops use is
        # precomputed once here instead of calling NetworkX on each call.
        g = self._graph
        self._concepts = tuple(sorted(g.nodes()))
        self._roots = tuple(sorted(n for n, d in g.in_degree() if d == 0))
        self._topo = tuple(nx.lexicographical_topological_sort(g))
        self._prereqs = {c: tuple(sorted(g.predecessors(c))) for c in self._concepts}
        self._ancestors = {c: frozenset(nx.ancestors(g, c)) for c in self._concepts}
        self._descendants = {c: frozenset(nx.descendants(g, c)) for c in self._concepts}
        self._depth: dict[str, int] = {}
        for node in self._topo:
            preds = self._prereqs[node]
            self._depth[node] = max((self._depth[p] for p in preds), default=-1) + 1
        self.fingerprint = hash((self._concepts, tuple(self._prereqs.items())))

    def _check(self, c: str) -> None:
        if c not in self._prereqs:
            raise UnknownConceptError(f"Concept {c} not in graph")

    @classmethod
    def from_concepts(cls, concepts: tuple[Concept, ...]) -> "CurriculumGraph":
        return cls(concepts)

    def concepts(self) -> tuple[str, ...]:
        return self._concepts

    def roots(self) -> tuple[str, ...]:
        return self._roots

    def prerequisites(self, c: str) -> tuple[str, ...]:
        self._check(c)
        return self._prereqs[c]

    def ancestors(self, c: str) -> frozenset[str]:
        self._check(c)
        return self._ancestors[c]

    def descendants(self, c: str) -> frozenset[str]:
        self._check(c)
        return self._descendants[c]

    def descendant_count(self, c: str) -> int:
        return len(self.descendants(c))

    def depth(self, c: str) -> int:
        self._check(c)
        return self._depth[c]

    def topological_order(self) -> tuple[str, ...]:
        return self._topo
