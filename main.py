import argparse
import sys
import os
from src.config.loader import load_constraints, load_anomalies, load_value_spaces
from src.engine.generator import GeneratorEngine
from src.mutator.registry import ActionRegistry
from src.io.renderers import JSONRenderer, JSONLRowRenderer
from src.io.exporters import LocalFileExporter, SingleFileBytesExporter
from src.engine.evaluator import MissingReferenceError, ExpressionSyntaxError
from src.engine.dag_builder import CyclicalDependencyError

def main():
    parser = argparse.ArgumentParser(description="Synthetic Invoice Generator V2")
    parser.add_argument("--config", type=str, default="constraints.yaml", help="Path to constraints.yaml")
    parser.add_argument("--anomalies", type=str, default="anomalies.yaml", help="Path to anomalies.yaml")
    parser.add_argument("--value-spaces", type=str, default="value_spaces.yaml", help="Path to value spaces")
    
    parser.add_argument("--count", type=int, default=10, help="Number of records to generate")
    parser.add_argument("--mutation-rate", type=float, default=0.0, help="Percentage of records to randomly mutate (0.0 - 1.0)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for perfect reproducibility")
    parser.add_argument("--preview", action="store_true", help="Print exactly 1 JSON object to stdout and exit")
    
    parser.add_argument("--output-format", choices=["json-files", "json-array", "jsonl"], default="json-files", help="Export structural target")
    parser.add_argument("--output-dir", type=str, default="output", help="Directory or filepath to emit data to.")
    
    args = parser.parse_args()

    # 1. Parsing Phase
    try:
        if not os.path.exists(args.config):
            print(f"Error: Base configuration file '{args.config}' not found.")
            sys.exit(1)
            
        constraints = load_constraints(args.config)
        anomalies = load_anomalies(args.anomalies) if os.path.exists(args.anomalies) else None
        value_spaces = load_value_spaces(args.value_spaces)
    except Exception as e:
        print(f"\n[Validation Error] Failed parsing YAML configuration: {str(e)}\n")
        sys.exit(1)

    if args.preview:
        args.count = 1
        args.mutation_rate = 0.0

    print(f"Initializing Generator (Count: {args.count}, Mutator Rate: {args.mutation_rate})...")

    # 2. Engine Spooling
    try:
        engine = GeneratorEngine(constraints, value_spaces, seed=args.seed)
        action_registry = ActionRegistry(anomalies, engine) if anomalies else None
    except CyclicalDependencyError as e:
        print(f"\n[Architecture Error] {str(e)}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Engine Boot Error] {str(e)}\n")
        sys.exit(1)

    # 3. Exporter Target Logic
    if args.output_format == "jsonl":
        renderer = JSONLRowRenderer()
        exporter = SingleFileBytesExporter(f"{args.output_dir}/dataset.jsonl")
    elif args.output_format == "json-array":
        renderer = JSONRenderer()
        exporter = SingleFileBytesExporter(f"{args.output_dir}/dataset.json")
    else:
        renderer = JSONRenderer()
        exporter = LocalFileExporter(args.output_dir)

    # 4. Iteration and Data Generation
    try:
        with exporter as writer:
            if args.output_format == "json-array" and not args.preview:
                writer.write("array", b"[\n")
                
            for i in range(args.count):
                import uuid
                batch_id = str(uuid.uuid4())[:8] if not args.seed else f"seed_{args.seed}"
                
                try:
                    record = engine.generate_record(batch_id, i)
                except (MissingReferenceError, ExpressionSyntaxError) as ux_err:
                    print(f"\n[Validation Error] Generating Record: {str(ux_err)}")
                    sys.exit(1)
                except Exception as eval_err:
                    print(f"\n[Runtime Error] Generating Record #{i}: {str(eval_err)}")
                    sys.exit(1)
                    
                if args.mutation_rate > 0.0 and action_registry:
                    import random
                    if random.random() < args.mutation_rate:
                        record = action_registry.mutate(record)
                    else:
                        record["_scenario_label"] = "clean"
                else:
                    record["_scenario_label"] = "clean"
                    
                payload_bytes = renderer.render(record)
                
                if args.preview:
                    print("\n" + payload_bytes.decode('utf-8'))
                    break
                    
                if args.output_format == "json-files":
                    writer.write(f"invoice_{batch_id}_{i}.json", payload_bytes)
                else:
                    writer.write("stream", payload_bytes)
                    if args.output_format == "json-array" and i < (args.count - 1):
                        writer.write("stream", b",\n")

            if args.output_format == "json-array" and not args.preview:
                writer.write("array", b"\n]\n")

    except Exception as io_err:
        print(f"\n[I/O Error] Writing outputs: {str(io_err)}\n")
        sys.exit(1)

    if not args.preview:
        print(f"\n[Done] Successfully built {args.count} synthetics inside `{args.output_dir}`.\n")

if __name__ == "__main__":
    main()
