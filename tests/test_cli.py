from regalias.cli import main


def _preparar(db, capsys, personas):
    for identificador, nombre in personas:
        assert main(["--db", db, "persona", "--id", identificador, "--nombre", nombre]) == 0
    capsys.readouterr()


def test_flujo_completo_por_linea_de_comandos(tmp_path, capsys):
    db = str(tmp_path / "regalias.sqlite")
    _preparar(db, capsys, [("ana@x.com", "Ana"), ("beto@x.com", "Beto")])

    assert main([
        "--db", db, "cancion", "--titulo", "Sol", "--artista", "Ana",
        "--colaborador", "ana@x.com:50", "--colaborador", "beto@x.com:50",
    ]) == 0
    assert main(["--db", db, "venta", "--cancion", "1", "--fecha", "2026-03-02",
                 "--precio", "10.00"]) == 0
    capsys.readouterr()

    assert main(["--db", db, "reporte", "--colaborador", "beto@x.com"]) == 0
    assert capsys.readouterr().out == "2026-03  5.00\n"


def test_tarifa_no_numerica_da_mensaje_claro(tmp_path, capsys):
    db = str(tmp_path / "regalias.sqlite")
    _preparar(db, capsys, [("ana@x.com", "Ana")])
    main(["--db", db, "cancion", "--titulo", "Sol", "--artista", "Ana",
          "--colaborador", "ana@x.com:100"])
    capsys.readouterr()

    codigo = main([
        "--db", db, "reproducciones", "--cancion", "1", "--fecha", "2026-03-10",
        "--cantidad", "5", "--tarifa", "abc",
    ])

    assert codigo == 1
    assert "inválido" in capsys.readouterr().err


def test_errores_de_negocio_salen_con_codigo_1_y_mensaje(tmp_path, capsys):
    db = str(tmp_path / "regalias.sqlite")
    _preparar(db, capsys, [("ana@x.com", "Ana"), ("beto@x.com", "Beto")])

    codigo = main([
        "--db", db, "cancion", "--titulo", "Sol", "--artista", "Ana",
        "--colaborador", "ana@x.com:60", "--colaborador", "beto@x.com:39.99",
    ])

    assert codigo == 1
    assert "100" in capsys.readouterr().err
