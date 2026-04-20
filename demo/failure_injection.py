import os
import argparse

def inject_failure(failure_type: str, fixture_dir: str):
    print(f"Injecting failure: {failure_type} into {fixture_dir}")
    
    if failure_type == "unit_mismatch":
        csv_path = os.path.join(fixture_dir, "warehouse_capacity.csv")
        if os.path.exists(csv_path):
            with open(csv_path, 'r') as f:
                content = f.read()
            # Deliberately modify units to force validation gate to trip
            content = content.replace("capacity_tons", "capacity_kg")
            with open(csv_path, 'w') as f:
                f.write(content)
            print("Unit mismatch injected (tons -> kg).")
        else:
            # Create a mock one
            os.makedirs(fixture_dir, exist_ok=True)
            with open(csv_path, 'w') as f:
                f.write("warehouse,capacity_kg\nW1,5000\nW2,8000\nW3,12000")
            print("Mock unit mismatch injected.")
            
    elif failure_type == "ambiguity":
        txt_path = os.path.join(fixture_dir, "instructions.txt")
        os.makedirs(fixture_dir, exist_ok=True)
        with open(txt_path, 'a') as f:
            f.write("\nAlso, optimize efficiency broadly.")
        print("Ambiguity injected into instructions.")
        
    elif failure_type == "infeasibility":
        txt_path = os.path.join(fixture_dir, "instructions.txt")
        os.makedirs(fixture_dir, exist_ok=True)
        with open(txt_path, 'a') as f:
            f.write("\nDemand must exceed 1,000,000 units while capacity is strictly 5,000.")
        print("Infeasibility constraints injected.")
        
    elif failure_type == "timeout":
        txt_path = os.path.join(fixture_dir, "instructions.txt")
        os.makedirs(fixture_dir, exist_ok=True)
        with open(txt_path, 'a') as f:
            f.write("\nScale variables up by 10,000x to force branch-and-bound exhaustion.")
        print("Timeout condition injected.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["unit_mismatch", "ambiguity", "infeasibility", "timeout"], required=True)
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()
    
    inject_failure(args.type, args.fixture)
