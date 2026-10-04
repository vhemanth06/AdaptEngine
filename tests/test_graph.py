import pytest
from adaptengine.core.schema import Concept
from adaptengine.core.errors import CycleError
from adaptengine.curriculum.graph import CurriculumGraph


def test_valid_dag():
    concepts = (Concept("C1"), Concept("C2"), Concept("C3", ("C1", "C2")), Concept("C4", ("C3",)))
    g = CurriculumGraph.from_concepts(concepts)

    assert set(g.roots()) == {"C1", "C2"}
    assert g.ancestors("C4") == {"C1", "C2", "C3"}
    assert g.descendants("C1") == {"C3", "C4"}

    assert g.descendant_count("C1") == 2
    assert g.descendant_count("C3") == 1
    assert g.descendant_count("C4") == 0

    assert g.depth("C1") == 0
    assert g.depth("C2") == 0
    assert g.depth("C3") == 1
    assert g.depth("C4") == 2

    order = g.topological_order()
    assert order == ("C1", "C2", "C3", "C4")

    # Stability test
    for _ in range(10):
        assert g.topological_order() == order

    assert g.prerequisites("C3") == ("C1", "C2")


# TC1.1: Load the prerequisite graph and inject a cycle. A valid graph is confirmed acyclic; a cycle is rejected at load time
def test_cycle_rejected():
    concepts = (Concept("C1", ("C2",)), Concept("C2", ("C1",)))
    with pytest.raises(CycleError) as exc:
        CurriculumGraph.from_concepts(concepts)
    assert "C1" in str(exc.value)


def test_self_loop_rejected():
    concepts = (Concept("C1", ("C1",)),)
    with pytest.raises(CycleError):
        CurriculumGraph.from_concepts(concepts)


def test_tc42_precursor_ignore_descriptions():
    c1 = Concept("C1", description="Detailed text")
    c1_blank = Concept("C1", description="")

    g1 = CurriculumGraph.from_concepts((c1,))
    g2 = CurriculumGraph.from_concepts((c1_blank,))

    assert g1.roots() == g2.roots()
    assert g1.topological_order() == g2.topological_order()
    assert g1.depth("C1") == g2.depth("C1")
