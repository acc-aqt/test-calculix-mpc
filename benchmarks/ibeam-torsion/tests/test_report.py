from analytical import analytical_solution
from benchmark_parameters import COARSE, IPE200_TORSION
from report import render_report
from runner import BenchmarkResult

VLASOV_TIP_TWIST = 0.26275


def result(level, tip_ratio=1.0):
    """A result record whose tip twist is the given ratio of the Vlasov target."""
    tip = VLASOV_TIP_TWIST * tip_ratio
    return BenchmarkResult(
        mesh_level=level,
        element_count=420,
        node_count=3164,
        twist_curve=((0.0, 0.0), (1500.0, tip / 3), (3000.0, tip)),
        analytical=analytical_solution(IPE200_TORSION),
    )


def test_report_states_solver_version_and_that_the_verdict_is_not_evaluated():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "Version 2.24" in text
    assert "not evaluated" in text


def test_report_lists_parameters_and_targets():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "T = 500000 N·mm about +x" in text
    assert "| J = (2·b·t_f³ + (h − 2t_f)·t_w³)/3 | 51654.2 mm⁴ |" in text
    assert "| φ(L), Vlasov (target) | 0.26275 rad |" in text
    assert "| φ_SV(L) = TL/(GJ) (information) | 0.35953 rad |" in text
    assert "58.68 MPa" in text and "148.84 MPa" in text and "69.10 MPa" in text


def test_report_lists_the_end_corrected_j_and_its_tip_twist_for_information():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "| J, end-corrected (information) | 49255.3 mm⁴ |" in text
    assert "| φ(L), Vlasov with end-corrected J (information) | 0.27313 rad |" in text


def test_convergence_row_shows_tip_twist_and_its_errors_against_vlasov_and_st_venant():
    text = render_report([result(COARSE, tip_ratio=1.05)], IPE200_TORSION, "Version 2.24")
    # 1.05 x 0.26275 = 0.27589 rad; against phi_SV: 0.275888 / 0.359533 - 1 = -23.27 %.
    assert "| coarse | 420 | 3164 | 0.27589 | +5.00 | -23.27 |" in text


def test_report_links_to_the_coupling_adr():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "0003" in text
