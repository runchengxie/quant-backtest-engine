"""Fast regressions for release source assembly; no compiler/network required."""

import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

import package_release


class PackageTests(TestCase):
    def test_supplement_lookup_uses_manifest_identity_not_vendor_directory_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = root / "vendor" / "nautilus-macros"
            crate.mkdir(parents=True)
            (crate / "Cargo.toml").write_text(
                '[package]\nname="nautilus-macros"\nversion="0.66.0"\nlicense="LGPL-3.0-only"\n'
            )
            with patch.object(
                package_release, "supplement_notices", return_value=[{"sha256": "test"}]
            ) as supplement:
                inventory = package_release.license_inventory(
                    crate.parent, root / "notices"
                )
            supplement.assert_called_once()
            self.assertEqual(inventory[0]["supplemental_notices"], [{"sha256": "test"}])

    def test_unknown_crate_without_notices_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = root / "vendor" / "unknown"
            crate.mkdir(parents=True)
            (crate / "Cargo.toml").write_text(
                '[package]\nname="unknown"\nversion="1.0.0"\n'
            )
            with self.assertRaisesRegex(RuntimeError, "No license/notice"):
                package_release.license_inventory(crate.parent, root / "notices")


if __name__ == "__main__":
    main()
