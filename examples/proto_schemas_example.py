import sys
import os
import time
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.struct_pb2 import Struct

# Add the generated code directory to the path so imports work
# Adjust this path based on where you ran the protoc command
sys.path.append(os.path.join(os.path.dirname(__file__), "generated/python"))

# Import generated classes
# Note: The package name in the proto file is 'iex.minibrain.v1'
try:
    import minibrain_pb2 as mb
    import minibrain_pb2_grpc as mb_grpc
except ImportError:
    # Placeholder for when the proto files haven't been compiled yet
    print("Error: Generated proto modules not found. Please run protoc first.")
    sys.exit(1)

def create_source_example() -> mb.Source:
    """
    Demonstrates how to create a Source message with metadata and timestamps.
    """
    print("--- Creating Source ---")
    
    # Create a Timestamp for 'now'
    now = Timestamp()
    now.GetCurrentTime()

    # Instantiate the Source message
    source = mb.Source(
        id="src-12345",
        uri="s3://bucket/videos/interview_01.mp4",
        type=mb.Source.SOURCE_TYPE_VIDEO,
        mime_type="video/mp4",
        created_at=now,
        version="1.0"
    )
    
    # Add metadata (map<string, string>)
    source.metadata["author"] = "Jane Doe"
    source.metadata["duration_sec"] = "120"

    print(f"Created Source: {source.id} ({source.uri})")
    return source

def create_evidence_with_locator(source_id: str) -> mb.EvidenceUnit:
    """
    Demonstrates how to create an EvidenceUnit with a specific 'oneof' locator.
    """
    print("\n--- Creating EvidenceUnit with VideoLocator ---")

    # Create the specific locator (VideoLocator)
    vid_loc = mb.VideoLocator(
        start_time_ms=15000,
        end_time_ms=25000,
        frame_index=450
    )

    # Instantiate EvidenceUnit
    # Note: We pass 'video_locator' to the constructor. 
    # In proto3, setting one field in a 'oneof' group automatically clears others.
    evidence = mb.EvidenceUnit(
        id="ev-999",
        source_id=source_id,
        artifact_id="art-transcription-1",
        content_snippet="The subject mentions the Q3 financial results here.",
        confidence_score=0.95,
        video_locator=vid_loc 
    )

    print(f"Created Evidence: {evidence.id}")
    print(f"Locator Type: {evidence.WhichOneof('locator')}") # Should print 'video_locator'
    print(f"Start Time: {evidence.video_locator.start_time_ms}ms")
    
    return evidence

def simulate_serialization(message):
    """
    Demonstrates serialization to bytes (for Kafka/Storage) and deserialization.
    """
    print(f"\n--- Serializing {type(message).__name__} ---")
    
    # Serialize to binary string
    serialized_data = message.SerializeToString()
    print(f"Serialized size: {len(serialized_data)} bytes")

    # Deserialize into a new object
    new_message = type(message)()
    new_message.ParseFromString(serialized_data)
    
    print("Deserialization successful.")
    return new_message

def simulate_grpc_interaction(source_obj: mb.Source):
    """
    Simulates constructing a gRPC request object.
    (Does not actually make a network call, just shows message construction).
    """
    print("\n--- Simulating gRPC Request Construction ---")
    
    # Construct the Request object defined in the service
    request = mb.SaveSourceRequest(source=source_obj)
    
    print(f"Prepared SaveSourceRequest for Source ID: {request.source.id}")
    
    # In a real app, you would do:
    # channel = grpc.insecure_channel('localhost:50051')
    # stub = mb_grpc.PersistenceServiceStub(channel)
    # response = stub.SaveSource(request)

def create_kafka_event(step_id: str, thread_id: str):
    """
    Demonstrates using Google Struct for dynamic payloads in Kafka events.
    """
    print("\n--- Creating Kafka Event (StepRequested) ---")
    
    # Create dynamic payload using google.protobuf.Struct
    payload = Struct()
    payload.update({
        "model_name": "gpt-4",
        "temperature": 0.7,
        "retry_count": 3
    })

    event = mb.StepRequested(
        trace_id="trace-abc-123",
        step_id=step_id,
        workflow_name="summarization_pipeline",
        thread_id=thread_id,
        input_payload=payload, # Assign the Struct
        priority=1
    )
    
    # Set timestamp
    event.requested_at.GetCurrentTime()

    print(f"Event Trace ID: {event.trace_id}")
    print(f"Payload keys: {list(event.input_payload.keys())}")

if __name__ == "__main__":
    # 1. Create a Source domain model
    my_source = create_source_example()

    # 2. Create Evidence linked to that source
    my_evidence = create_evidence_with_locator(my_source.id)

    # 3. Serialize/Deserialize the evidence
    restored_evidence = simulate_serialization(my_evidence)
    assert restored_evidence.content_snippet == my_evidence.content_snippet

    # 4. Prepare a gRPC request
    simulate_grpc_interaction(my_source)

    # 5. Create a Kafka event message
    create_kafka_event("step-gen-summary", "thread-555")