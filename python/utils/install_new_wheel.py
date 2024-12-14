import os
import re
import subprocess
import sys

from nxs_python.utils.encrypt_decrypt import decrypt_file, key
from pathlib import Path


def main():
    wheel_pattern = r'^rpi_final_acceptance_test-(\d+\.\d+(\.\d+)?(\.dev\d+)?)-py3-none-any\.ewhl$'

    print('looking for encrypted wheel files')
    files = os.listdir('files')
    for file in files:
        if re.match(wheel_pattern, file):
            basename = Path(f'files/{file}').with_suffix('')
            print(f'decrypting {basename}.ewhl to {basename}.whl')
            decrypt_file(f'{basename}.ewhl', f'{basename}.whl', key)
            os.remove(f'{basename}.ewhl')
            print(f'Installing {basename}.whl')
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', f'{basename}.whl'])
            os.remove(f'{basename}.whl')


if __name__ == '__main__':
    main()
