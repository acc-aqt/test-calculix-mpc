from records import result

from benchmark_parameters import COARSE, FINE, LE10, MEDIUM
from deck import C3D20
from report import render_report


def test_report_states_solver_version_and_that_the_verdict_is_not_evaluated():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "Version 2.24" in text
    assert "not evaluated" in text


def test_report_lists_the_le10_parameters():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "| Inner ellipse (hole edge) | a_i = 2000, b_i = 1000 mm |" in text
    assert "| Outer ellipse | a_o = 3250, b_o = 2750 mm |" in text
    assert "| Thickness | t = 600 mm, z from −300 to +300 mm |" in text
    assert "| Material | E = 210000 MPa, ν = 0.3 |" in text
    assert "| Load | p = 1 MPa on the top face (z = +300 mm) |" in text


def test_report_states_the_published_target_and_its_provenance():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "| σ_yy(D), published (target) | −5.38 MPa |" in text
    assert "TNSB Rev. 3" in text and "not consulted" in text
    assert "0004" in text


def test_level_row_shows_sigma_yy_at_d_its_signed_error_and_the_integration_point_value():
    text = render_report([result(COARSE, stress_ratio=1.05)], LE10, "Version 2.24")
    # 1.05 x -5.38 = -5.649 MPa, +5.00 % against -5.38 MPa.
    assert "| coarse 6×4×2 | 48 | 349 | -5.649 | +5.00 | -3.820 |" in text


def test_report_shows_the_stress_tensor_and_von_mises_at_d():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "| coarse | -0.357 | -5.380 | -1.085 | 0.060 | -0.019 | -0.054 | 4.704 |" in text


def test_c3d20_rows_sit_beside_the_c3d20r_rows_for_information():
    results = [result(COARSE, 1.05), result(COARSE, 1.10, element_type=C3D20)]
    text = render_report(results, LE10, "Version 2.24")
    # C3D20R -5.649 MPa; C3D20 1.10 x -5.38 = -5.918 MPa, +10.00 %.
    assert "| coarse 6×4×2 | -5.649 | -5.918 | +10.00 | -3.820 |" in text
    assert "C3D20 (information)" in text


def test_c3d20_values_never_count():
    reduced = [result(COARSE, 1.01), result(MEDIUM, 1.005), result(FINE, 1.0)]
    far_off = [result(level, 2.0, element_type=C3D20) for level in (COARSE, MEDIUM, FINE)]
    with_c3d20 = render_report(reduced + far_off, LE10, "Version 2.24")
    without = render_report(reduced, LE10, "Version 2.24")

    def counted(text):
        lines = text.splitlines()
        verdict = [line for line in lines if line.startswith("- Verdict")]
        start = lines.index("## Mesh levels") + 1
        end = next(n for n in range(start, len(lines)) if lines[n].startswith("## "))
        return verdict, lines[start:end]

    assert counted(with_c3d20) == counted(without)
