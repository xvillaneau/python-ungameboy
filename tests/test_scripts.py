
from ungameboy.address import Address
from ungameboy.dis import Disassembler
from ungameboy.scripts import ScriptsManager


def test_script_discover():
    asm = Disassembler()
    scripts = ScriptsManager(asm)

    scripts.discover_scripts("ungameboy.extras.wl2")
    assert "wl2" in scripts.scripts
    wl2 = scripts.scripts["wl2"]
    assert "rle_block" in wl2

    group = scripts.get_commands()
    cmd, _ = group.get_handler("run wl2 rle_block")
    assert len(cmd.args) == 1
    assert cmd.args[0].annotation is Address
