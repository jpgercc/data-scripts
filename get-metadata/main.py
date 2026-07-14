import sys
import os
import subprocess
import shutil
import platform
import json

class LookIn:
    def __init__(self, file_path):
        self.file_path = file_path
        self.os = platform.system()
        self.validate_environment()

    def validate_environment(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Arquivo ausente: {self.file_path}")
        if not shutil.which("exiftool"):
            raise EnvironmentError("exiftool ausente.")
        if self.os != "Windows" and not shutil.which("strings"):
            raise EnvironmentError("strings ausente.")

    def get_file_info(self):
        stats = os.stat(self.file_path)
        
        # Identificação técnica (assinatura real via MIME)
        mime = subprocess.check_output(["exiftool", "-mimeType", "-s3", self.file_path]).decode().strip()
        
        return {
            "tamanho_bytes": stats.st_size,
            "assinatura_tecnica": mime
        }

    def get_metadata(self):
        raw = subprocess.check_output(["exiftool", "-j", self.file_path])
        return json.loads(raw)[0]

    def get_strings(self):
        # Uso de strings binário
        cmd = ["strings", self.file_path]
        raw = subprocess.check_output(cmd).decode(errors="ignore")
        return raw.splitlines()[:50]

    def process(self):
        return {
            "tamanho_e_assinatura": self.get_file_info(),
            "metadados": self.get_metadata(),
            "strings": self.get_strings()
        }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
        
    engine = LookIn(sys.argv[1])
    report = engine.process()
    print(json.dumps(report, indent=4))
    
    if input("\nSalvar (s/n)? ").lower() == 's':
        with open("analise.json", "w") as f:
            json.dump(report, f)