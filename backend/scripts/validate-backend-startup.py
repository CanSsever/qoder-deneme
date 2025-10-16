#!/usr/bin/env python3
"""
Backend Startup Validation Service
Ensures backend is correctly configured for mobile device access
"""

import socket
import requests
import sys
import subprocess
import platform
from typing import List, Tuple, Optional

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class BackendValidator:
    def __init__(self, port: int = 8000):
        self.port = port
        self.issues: List[str] = []
        self.warnings: List[str] = []
        
    def print_header(self):
        """Print validation header"""
        print("=" * 60)
        print(f"{BOLD}OneShot Backend Startup Validator{RESET}")
        print("=" * 60)
        print()

    def check_port_availability(self) -> bool:
        """Check if port is available or already in use"""
        print(f"Checking port {self.port} availability...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        
        try:
            result = sock.connect_ex(('localhost', self.port))
            if result == 0:
                # Port is in use
                print(f"{YELLOW}⚠ Port {self.port} is already in use{RESET}")
                self.warnings.append(f"Port {self.port} is in use. Make sure it's your backend server.")
                return False
            else:
                print(f"{GREEN}✓ Port {self.port} is available{RESET}")
                return True
        except Exception as e:
            print(f"{RED}✗ Error checking port: {e}{RESET}")
            self.issues.append(f"Cannot check port {self.port}: {e}")
            return False
        finally:
            sock.close()

    def get_network_interfaces(self) -> List[Tuple[str, str]]:
        """Get all network interface IP addresses"""
        import netifaces
        
        interfaces = []
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr['addr']
                    if not ip.startswith('127.'):
                        interfaces.append((interface, ip))
        return interfaces

    def check_health_endpoint(self, url: str, timeout: int = 5) -> Optional[int]:
        """Check if health endpoint is responding"""
        try:
            response = requests.get(f"{url}/healthz", timeout=timeout)
            return response.status_code
        except Exception as e:
            return None

    def validate_backend_accessible(self) -> bool:
        """Validate backend is accessible from network"""
        print("\\nValidating backend accessibility...")
        
        # Check localhost
        print(f"Testing localhost access...")
        status = self.check_health_endpoint(f"http://localhost:{self.port}")
        if status == 200:
            print(f"{GREEN}✓ Backend accessible on localhost{RESET}")
        else:
            print(f"{RED}✗ Backend not accessible on localhost{RESET}")
            self.issues.append("Backend not responding on localhost")
            return False

        # Check network interfaces
        try:
            interfaces = self.get_network_interfaces()
            
            if not interfaces:
                print(f"{YELLOW}⚠ No network interfaces found{RESET}")
                self.warnings.append("No network interfaces detected")
                return True  # localhost works, that's minimum
            
            print(f"\\nTesting network interface access...")
            accessible_ips = []
            
            for interface, ip in interfaces:
                status = self.check_health_endpoint(f"http://{ip}:{self.port}", timeout=3)
                if status == 200:
                    print(f"{GREEN}✓ Accessible on {interface} ({ip}){RESET}")
                    accessible_ips.append(ip)
                else:
                    print(f"{YELLOW}⚠ Not accessible on {interface} ({ip}){RESET}")
            
            if accessible_ips:
                print(f"{GREEN}✓ Backend accessible from network{RESET}")
                return True
            else:
                print(f"{RED}✗ Backend not accessible from any network interface{RESET}")
                self.issues.append("Backend is not accessible from network. Check binding and firewall.")
                return False
                
        except ImportError:
            print(f"{YELLOW}⚠ Cannot check network interfaces (netifaces not installed){RESET}")
            self.warnings.append("Install 'netifaces' for network interface checking")
            return True

    def check_firewall(self) -> bool:
        """Check firewall configuration (platform-specific)"""
        print(f"\\nChecking firewall configuration...")
        
        system = platform.system()
        
        if system == "Windows":
            # Check Windows Firewall
            try:
                result = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "show", "rule", f"name=all"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # Look for rules allowing port
                if f"LocalPort:                         {self.port}" in result.stdout:
                    print(f"{GREEN}✓ Firewall rule exists for port {self.port}{RESET}")
                    return True
                else:
                    print(f"{YELLOW}⚠ No firewall rule found for port {self.port}{RESET}")
                    self.warnings.append(f"Consider adding firewall rule for port {self.port}")
                    return False
            except Exception as e:
                print(f"{YELLOW}⚠ Cannot check Windows Firewall: {e}{RESET}")
                return True
                
        elif system == "Linux":
            # Check iptables or ufw
            try:
                # Check if ufw is installed
                result = subprocess.run(["which", "ufw"], capture_output=True)
                if result.returncode == 0:
                    result = subprocess.run(["ufw", "status"], capture_output=True, text=True)
                    if f"{self.port}" in result.stdout or "inactive" in result.stdout.lower():
                        print(f"{GREEN}✓ Firewall allows port {self.port} or is inactive{RESET}")
                        return True
                    else:
                        print(f"{YELLOW}⚠ Firewall may block port {self.port}{RESET}")
                        return False
                else:
                    print(f"{BLUE}ℹ No firewall detected (ufw not installed){RESET}")
                    return True
            except Exception as e:
                print(f"{YELLOW}⚠ Cannot check firewall: {e}{RESET}")
                return True
                
        else:
            print(f"{BLUE}ℹ Firewall check not implemented for {system}{RESET}")
            return True

    def generate_access_urls(self):
        """Generate and display access URLs"""
        print("\\n" + "=" * 60)
        print(f"{BOLD}Network Configuration{RESET}")
        print("=" * 60)
        
        print(f"\\nLocalhost:        http://localhost:{self.port}")
        
        try:
            interfaces = self.get_network_interfaces()
            
            if interfaces:
                print("\\nNetwork Interfaces:")
                for interface, ip in interfaces:
                    print(f"  {interface:12} http://{ip}:{self.port}")
        except ImportError:
            pass

        print("\\n" + "=" * 60)
        print(f"{BOLD}Mobile Access URLs{RESET}")
        print("=" * 60)
        
        print(f"\\nAndroid Emulator: http://10.0.2.2:{self.port}")
        print(f"iOS Simulator:    http://localhost:{self.port}")
        
        try:
            interfaces = self.get_network_interfaces()
            if interfaces:
                # Use first non-localhost interface for physical devices
                primary_ip = interfaces[0][1] if interfaces else "192.168.1.x"
                print(f"Physical Devices: http://{primary_ip}:{self.port}")
        except ImportError:
            print(f"Physical Devices: http://192.168.1.x:{self.port}")

        print("\\n" + "=" * 60)
        print(f"{BOLD}Quick Test Commands{RESET}")
        print("=" * 60)
        
        print(f"\\ncurl http://localhost:{self.port}/healthz")
        
        try:
            interfaces = self.get_network_interfaces()
            if interfaces:
                primary_ip = interfaces[0][1]
                print(f"curl http://{primary_ip}:{self.port}/healthz")
        except ImportError:
            pass

        print(f"\\nAPI Documentation: http://localhost:{self.port}/docs")
        print()

    def print_summary(self):
        """Print validation summary"""
        print("=" * 60)
        print(f"{BOLD}Validation Summary{RESET}")
        print("=" * 60)
        print()
        
        if not self.issues and not self.warnings:
            print(f"{GREEN}{BOLD}✓ All checks passed!{RESET}")
            print(f"{GREEN}Backend is ready for mobile development.{RESET}")
        else:
            if self.issues:
                print(f"{RED}{BOLD}Issues Found:{RESET}")
                for issue in self.issues:
                    print(f"  {RED}✗{RESET} {issue}")
                print()
            
            if self.warnings:
                print(f"{YELLOW}{BOLD}Warnings:{RESET}")
                for warning in self.warnings:
                    print(f"  {YELLOW}⚠{RESET} {warning}")
                print()

            if self.issues:
                print(f"{RED}Please fix the issues above before starting development.{RESET}")
            else:
                print(f"{YELLOW}Backend is functional but some warnings should be addressed.{RESET}")
        
        print("=" * 60)

    def run(self):
        """Run all validation checks"""
        self.print_header()
        
        # Run checks
        port_available = self.check_port_availability()
        backend_accessible = self.validate_backend_accessible()
        self.check_firewall()
        
        # Generate URLs
        self.generate_access_urls()
        
        # Print summary
        self.print_summary()
        
        # Return exit code
        return 0 if not self.issues else 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate OneShot backend configuration")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Backend port to validate (default: 8000)"
    )
    
    args = parser.parse_args()
    
    validator = BackendValidator(port=args.port)
    exit_code = validator.run()
    
    sys.exit(exit_code)
