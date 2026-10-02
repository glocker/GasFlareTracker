from app.etl.known_coordinates import lookup


def test_port_arthur_known_coordinates_distinguish_neighboring_refineries() -> None:
    motiva = lookup("SAUDI ARAMCO", "Texas", "PORT ARTHUR")
    valero = lookup("VALERO ENERGY CORP", "Texas", "PORT ARTHUR")

    assert motiva == (-93.9510, 29.8886)
    assert valero == (-93.9634, 29.8654)
    assert motiva != valero
