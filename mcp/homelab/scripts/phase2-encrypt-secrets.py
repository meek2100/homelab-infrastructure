#!/usr/bin/env python3

import os
import glob
import subprocess

def encrypt_env_files():
    # Find all stack.env files in the new directory structure
    env_files = glob.glob("nodes/*/*-stacks/*/stack.env")
    
    print(f"Found {len(env_files)} stack.env files to encrypt.")
    
    # We must set SOPS_AGE_KEY_FILE environment variable
    sops_env = os.environ.copy()
    sops_env["SOPS_AGE_KEY_FILE"] = os.path.abspath("master-age-key.txt")
    
    for env_path in env_files:
        dir_path = os.path.dirname(env_path)
        enc_yaml_path = os.path.join(dir_path, "secrets.enc.yaml")
        
        # Run SOPS
        # Since we have .sops.yaml in root, sops knows the age key
        cmd = [
            os.path.expanduser("~/.local/bin/sops"),
            "--encrypt",
            "--input-type", "dotenv",
            "--output-type", "yaml",
            env_path
        ]
        
        try:
            with open(enc_yaml_path, 'w') as out_f:
                res = subprocess.run(cmd, stdout=out_f, stderr=subprocess.PIPE, env=sops_env)
                
            if res.returncode == 0:
                print(f"  ✓ Encrypted {env_path} -> {enc_yaml_path}")
                os.remove(env_path)
            else:
                print(f"  ❌ Failed to encrypt {env_path}: {res.stderr.decode('utf-8')}")
        except Exception as e:
            print(f"  ❌ Error encrypting {env_path}: {e}")

if __name__ == "__main__":
    if not os.path.exists("master-age-key.txt"):
        print("Error: master-age-key.txt not found. Please generate it first.")
        exit(1)
        
    encrypt_env_files()
    print("\n✅ Encryption complete. Plaintext env files have been deleted.")
