"""Update detection: what counts as newer, and when it is safe to act."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core import updater
from core.version import INSTALLER_SUFFIX, version_tuple


def release_json(tag, *, assets=("NeekoDraftAssistant-9.9.9-Setup.exe",),
                 draft=False, prerelease=False, body="", name=""):
    return {
        "tag_name": tag,
        "name": name or tag,
        "body": body,
        "draft": draft,
        "prerelease": prerelease,
        "assets": [
            {
                "name": asset,
                "browser_download_url": f"https://example.invalid/{asset}",
                "size": 1234,
            }
            for asset in assets
        ],
    }


class VersionTest(unittest.TestCase):
    def test_parses_plain_versions(self):
        self.assertEqual(version_tuple("1.2.3"), (1, 2, 3))

    def test_parses_tags_and_suffixes(self):
        self.assertEqual(version_tuple("v1.2.3"), (1, 2, 3))
        self.assertEqual(version_tuple("v2.0.0-beta.1"), (2, 0, 0))
        self.assertEqual(version_tuple("1.4"), (1, 4, 0))

    def test_junk_does_not_raise(self):
        self.assertEqual(version_tuple("not-a-version"), (0, 0, 0))

    def test_versions_compare_numerically(self):
        # The trap a string comparison falls into.
        self.assertGreater(version_tuple("1.10.0"), version_tuple("1.9.0"))


class ParseReleasesTest(unittest.TestCase):
    def test_finds_a_newer_release(self):
        found = updater.parse_releases([release_json("v1.0.1")], "1.0.0")

        self.assertIsNotNone(found)
        self.assertEqual(found.version, "1.0.1")
        self.assertTrue(found.installer_url.endswith(INSTALLER_SUFFIX))

    def test_same_version_is_not_an_update(self):
        self.assertIsNone(updater.parse_releases([release_json("v1.0.0")], "1.0.0"))

    def test_older_version_is_not_an_update(self):
        self.assertIsNone(updater.parse_releases([release_json("v0.9.0")], "1.0.0"))

    def test_picks_the_newest_of_several(self):
        payload = [release_json("v1.0.1"), release_json("v1.2.0"), release_json("v1.1.0")]

        self.assertEqual(updater.parse_releases(payload, "1.0.0").version, "1.2.0")

    def test_drafts_are_ignored(self):
        self.assertIsNone(
            updater.parse_releases([release_json("v2.0.0", draft=True)], "1.0.0")
        )

    def test_prereleases_are_ignored_unless_asked_for(self):
        payload = [release_json("v2.0.0", prerelease=True)]

        self.assertIsNone(updater.parse_releases(payload, "1.0.0"))
        self.assertIsNotNone(
            updater.parse_releases(payload, "1.0.0", allow_prerelease=True)
        )

    def test_a_release_without_an_installer_is_skipped(self):
        payload = [release_json("v1.5.0", assets=("source.zip", "notes.txt"))]

        self.assertIsNone(updater.parse_releases(payload, "1.0.0"))

    def test_falls_back_to_an_older_release_that_does_have_an_installer(self):
        payload = [
            release_json("v2.0.0", assets=("source.zip",)),
            release_json("v1.5.0"),
        ]

        self.assertEqual(updater.parse_releases(payload, "1.0.0").version, "1.5.0")

    def test_release_notes_are_carried_through(self):
        payload = [release_json("v1.1.0", body="  Neeko learned a new trick.  ")]

        self.assertEqual(updater.parse_releases(payload, "1.0.0").notes,
                         "Neeko learned a new trick.")

    def test_a_single_object_is_accepted(self):
        # GitHub's /releases/latest returns one object rather than a list.
        self.assertIsNotNone(updater.parse_releases(release_json("v1.1.0"), "1.0.0"))

    def test_nonsense_payloads_raise_rather_than_crash(self):
        for payload in ("not json", 42, None):
            with self.subTest(payload=payload):
                with self.assertRaises(updater.UpdateError):
                    updater.parse_releases(payload, "1.0.0")

    def test_junk_entries_inside_the_list_are_skipped(self):
        payload = ["nonsense", {"no_tag": True}, release_json("v1.1.0")]

        self.assertEqual(updater.parse_releases(payload, "1.0.0").version, "1.1.0")

    def test_an_empty_release_list_means_no_update(self):
        self.assertIsNone(updater.parse_releases([], "1.0.0"))


class BusyStateTest(unittest.TestCase):
    def test_a_draft_or_a_game_blocks_the_update(self):
        for state in ("READY_CHECK", "CHAMP_SELECT", "MY_TURN", "LOCKED", "IN_GAME"):
            with self.subTest(state=state):
                self.assertTrue(updater.is_busy(state))

    def test_idle_states_allow_it(self):
        for state in ("DISCONNECTED", "WAITING", "LOBBY", "QUEUED", "POST_GAME"):
            with self.subTest(state=state):
                self.assertFalse(updater.is_busy(state))

    def test_an_unknown_state_is_treated_as_free(self):
        self.assertFalse(updater.is_busy(None))
        self.assertFalse(updater.is_busy(""))


class SettingsSurviveTest(unittest.TestCase):
    def test_settings_live_outside_the_program_folder(self):
        # An installer replaces its own directory wholesale, so a config kept
        # inside it would be wiped by every update.
        from core.settings import CONFIG_DIR
        from core.paths import program_dir

        try:
            Path(CONFIG_DIR).resolve().relative_to(Path(program_dir()).resolve())
        except ValueError:
            return  # separate, which is what we want
        self.fail(f"settings at {CONFIG_DIR} would be destroyed by an update")

    def test_the_check_reports_safe_in_a_checkout(self):
        self.assertTrue(updater.settings_survive_update())

    def test_settings_written_before_an_update_are_still_there_after(self):
        from core.settings import Settings

        with TemporaryDirectory() as appdata, TemporaryDirectory() as program:
            config = Path(appdata) / "config.json"
            before = Settings.load(config)
            before.preferred_champion_id = 518
            before.preferred_champion_name = "Neeko"
            before.chat_message = "neeko says hi :)"
            before.accepted_total = 41
            before.save(config)

            # Whatever an update does to the program folder, it does not touch
            # the config directory.
            (Path(program) / "NeekoDraftAssistant.exe").write_text("old build")
            for item in Path(program).iterdir():
                item.unlink()
            (Path(program) / "NeekoDraftAssistant.exe").write_text("new build")

            after = Settings.load(config)

        self.assertEqual(after.preferred_champion_id, 518)
        self.assertEqual(after.preferred_champion_name, "Neeko")
        self.assertEqual(after.chat_message, "neeko says hi :)")
        self.assertEqual(after.accepted_total, 41)


class InstallTest(unittest.TestCase):
    def test_a_missing_installer_is_refused(self):
        with self.assertRaises(updater.UpdateError):
            updater.install(Path("nowhere") / "NeekoDraftAssistant-Setup.exe")

    def test_the_switches_keep_the_install_silent_and_restart_the_app(self):
        self.assertIn("/SILENT", updater.INSTALL_SWITCHES)
        self.assertIn("/CLOSEAPPLICATIONS", updater.INSTALL_SWITCHES)
        self.assertIn("/RESTARTAPPLICATIONS", updater.INSTALL_SWITCHES)


class BuildConfigurationTest(unittest.TestCase):
    """The build files have to agree with core/version.py."""

    ROOT = Path(__file__).resolve().parent.parent

    def test_the_installer_script_takes_its_version_from_the_build(self):
        script = (self.ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")

        self.assertIn("#ifndef AppVersion", script)
        self.assertIn("OutputBaseFilename={#AppShortName}-{#AppVersion}-Setup", script)
        self.assertIn("PrivilegesRequired=lowest", script)

    def test_the_installer_name_matches_what_the_updater_looks_for(self):
        script = (self.ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")

        self.assertTrue(INSTALLER_SUFFIX.endswith("-Setup.exe"))
        self.assertIn("-Setup", script)

    def test_the_installer_does_not_delete_user_settings(self):
        script = (self.ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
        deletions = [
            line for line in script.splitlines()
            if line.strip().startswith("Type:") and "userappdata" in line
        ]

        self.assertEqual(deletions, [], "an uninstall must not remove her settings")

    def test_the_spec_bundles_the_assets(self):
        spec = (self.ROOT / "packaging" / "neeko.spec").read_text(encoding="utf-8")

        self.assertIn('"assets"', spec)

    def test_a_released_build_never_opens_a_console(self):
        # A console build can be asked for while debugging, but only ever by
        # setting NEEKO_CONSOLE, and the release workflow must not set it.
        spec = (self.ROOT / "packaging" / "neeko.spec").read_text(encoding="utf-8")
        workflow = (self.ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("console=True", spec)
        self.assertIn("NEEKO_CONSOLE", spec)
        self.assertNotIn("NEEKO_CONSOLE", workflow)

    def test_the_release_workflow_runs_the_tests_before_building(self):
        workflow = (self.ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        tests_at = workflow.index("unittest")
        build_at = workflow.index("tools/build.py")

        self.assertLess(tests_at, build_at, "a release must never skip the tests")


if __name__ == "__main__":
    unittest.main()
