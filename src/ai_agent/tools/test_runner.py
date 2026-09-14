import subprocess


class TestRunner:
    def run(self):
        result = subprocess.run(
            ['pytest', '-q'],
            capture_output=True,
            text=True
        )
        return {
            'success': result.returncode == 0,
            'output': result.stdout + result.stderr
        }
