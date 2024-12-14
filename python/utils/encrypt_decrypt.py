import argparse
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pathlib import Path

# AES encryption key
key = bytes([0x32, 0x44, 0x6e, 0xca, 0xd9, 0x5c, 0x42, 0x9e, 0xeb, 0x33, 0xb9, 0x61, 0x9d, 0x8f, 0x52, 0x30,
             0xdd, 0x8, 0x85, 0xb4, 0x78, 0x69, 0x8c, 0x65, 0x30, 0x2d, 0x9c, 0x4a, 0x6e, 0x51, 0xe2, 0x17])


def encrypt_file(input_file, output_file, key, iv):
    """Encrypts a file using AES encryption (CBC mode) and writes the result to the output file.

    The input file content is padded using PKCS7 padding before encryption.

    Args:
        input_file (str): Path to the file to be encrypted.
        output_file (str): Path where the encrypted file will be saved.
        key (bytes): The encryption key.
        iv (bytes): Initialization vector for AES encryption.
    """
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    with open(input_file, 'rb') as f:
        plaintext = f.read()

    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(plaintext) + padder.finalize()

    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    with open(output_file, 'wb') as f:
        f.write(iv + ciphertext)


def decrypt_file(input_file, output_file, key):
    """Decrypts an AES-encrypted file (CBC mode) and writes the plaintext to the output file.

    The decrypted data is unpadded using PKCS7 padding.

    Args:
        input_file (str): Path to the encrypted file to be decrypted.
        output_file (str): Path where the decrypted file will be saved.
        key (bytes): The decryption key.
    """
    with open(input_file, 'rb') as f:
        iv = f.read(16)  # AES block size is 16 bytes
        ciphertext = f.read()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

    with open(output_file, 'wb') as f:
        f.write(plaintext)


def process_file(filename):
    """Determines whether to encrypt or decrypt a file based on its extension.

    If the file has a `.log` or `.whl` extension, it will be encrypted to `.elog` or `.ewhl`, respectively.
    If the file has a `.elog` or `.ewhl` extension, it will be decrypted to `.log` or `.whl`, respectively.

    Args:
        filename (str): Path to the file to be processed.
    """
    iv = os.urandom(16)
    file_path = Path(filename)
    ext = file_path.suffix

    if ext == '.log':
        output_file = file_path.with_suffix('.elog')
        encrypt_file(filename, output_file, key, iv)
        print(f'File {filename} encrypted to {output_file}')
    elif ext == '.whl':
        output_file = file_path.with_suffix('.ewhl')
        encrypt_file(filename, output_file, key, iv)
        print(f'File {filename} encrypted to {output_file}')
    elif ext == '.elog':
        output_file = file_path.with_suffix('.log')
        decrypt_file(filename, output_file, key)
        print(f'File {filename} decrypted to {output_file}')
    elif ext == '.ewhl':
        output_file = file_path.with_suffix('.whl')
        decrypt_file(filename, output_file, key)
        print(f'File {filename} decrypted to {output_file}')
    else:
        print(f'Unsupported file extension: {ext}. Only .log, .whl, .elog, and .ewhl are supported.')


def main():
    """Parses the command-line argument for the file and calls the process_file function."""
    parser = argparse.ArgumentParser(description='Encrypt or decrypt a file based on its extension.')
    parser.add_argument('filename', help='File to process')

    args = parser.parse_args()
    process_file(args.filename)


if __name__ == '__main__':
    main()
