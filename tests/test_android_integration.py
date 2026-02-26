#
# Copyright (C) 2026 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import unittest
import subprocess
import os
import shutil


class AndroidIntegrationTest(unittest.TestCase):

  def setUp(self):
    self.out_dir = "tmp"
    if os.path.exists(self.out_dir):
      shutil.rmtree(self.out_dir)
    os.makedirs(self.out_dir)

  def tearDown(self):
    if os.path.exists(self.out_dir):
      shutil.rmtree(self.out_dir)

  def test_torq_run(self):
    # Check for adb existence
    adb_path = shutil.which("adb")
    if adb_path is None:
      self.skipTest(
          f"adb not found in PATH. Current PATH: {os.environ.get('PATH')}")

    # Find torq executable
    torq_path = shutil.which("torq")
    if not torq_path:
      # Fallback for Bazel local execution
      for p in ["./torq", "./bazel-bin/torq"]:
        if os.path.exists(p) and os.access(p, os.X_OK):
          torq_path = p
          break

    self.assertIsNotNone(
        torq_path,
        "torq executable not found. Ensure it is built: bazel build //:torq")

    # Check for connected device
    result = subprocess.run([adb_path, "devices"],
                            capture_output=True,
                            text=True)
    lines = result.stdout.strip().split('\n')
    device_lines = [l for l in lines[1:] if l.strip()]
    if not device_lines:
      self.skipTest("No device connected")

    cmd = [torq_path, "-d", "3000", "--no-ui", "-o", self.out_dir]

    # Execute torq
    subprocess.run(cmd, check=True, env=os.environ)

    # Verify output
    files = os.listdir(self.out_dir)
    self.assertTrue(len(files) > 0, "Output directory is empty")
    self.assertTrue(
        any(f.endswith(".perfetto-trace") for f in files),
        f"No .perfetto-trace file found in {self.out_dir}. Files: {files}")


if __name__ == '__main__':
  unittest.main()
