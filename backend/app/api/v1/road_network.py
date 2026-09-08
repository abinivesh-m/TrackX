"""Admin endpoints for road network management."""

from typing import List
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_db
from app.models.road_network import RoadNetwork
from app.schemas.road_network import RoadNetworkCreate, RoadNetworkResponse

router = APIRouter(
    prefix="/admin/road-network",
    tags=["admin"],
    dependencies=[],  # Add auth dependency here in production
)


@router.get("", response_model=List[RoadNetworkResponse])
def list_road_connections(db: Session = Depends(get_db)):
    """List all road network connections."""
    connections = db.query(RoadNetwork).order_by(RoadNetwork.camera_a, RoadNetwork.camera_b).all()
    return [c.to_dict() for c in connections]


@router.get("/{camera_id}", response_model=List[RoadNetworkResponse])
def get_camera_connections(camera_id: str, db: Session = Depends(get_db)):
    """Get all connections for a specific camera."""
    connections = db.query(RoadNetwork).filter(
        (RoadNetwork.camera_a == camera_id) | (RoadNetwork.camera_b == camera_id)
    ).all()
    return [c.to_dict() for c in connections]


@router.post("", response_model=RoadNetworkResponse, status_code=status.HTTP_201_CREATED)
def create_road_connection(connection: RoadNetworkCreate, db: Session = Depends(get_db)):
    """Create a new road network connection."""
    # Check if connection already exists (bidirectional)
    existing = db.query(RoadNetwork).filter(
        ((RoadNetwork.camera_a == connection.camera_a) & (RoadNetwork.camera_b == connection.camera_b)) |
        ((RoadNetwork.camera_a == connection.camera_b) & (RoadNetwork.camera_b == connection.camera_a))
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connection already exists between these cameras"
        )
    
    db_connection = RoadNetwork(**connection.dict())
    db.add(db_connection)
    db.commit()
    db.refresh(db_connection)
    return db_connection.to_dict()


@router.put("/{connection_id}", response_model=RoadNetworkResponse)
def update_road_connection(connection_id: int, connection: RoadNetworkCreate, db: Session = Depends(get_db)):
    """Update a road network connection."""
    db_connection = db.query(RoadNetwork).filter(RoadNetwork.id == connection_id).first()
    if not db_connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    for key, value in connection.dict().items():
        setattr(db_connection, key, value)
    
    db.commit()
    db.refresh(db_connection)
    return db_connection.to_dict()


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_road_connection(connection_id: int, db: Session = Depends(get_db)):
    """Delete a road network connection."""
    db_connection = db.query(RoadNetwork).filter(RoadNetwork.id == connection_id).first()
    if not db_connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    db.delete(db_connection)
    db.commit()
    return None


@router.post("/seed", response_model=dict)
def seed_road_network(db: Session = Depends(get_db)):
    """Seed road network from hardcoded camera network (admin use only)."""
    # Import here to avoid circular dependency
    from network.camera_network import ROAD_GRAPH
    
    # Clear existing
    db.query(RoadNetwork).delete()
    db.commit()
    
    # Populate from ROAD_GRAPH
    count = 0
    for (cam_a, cam_b), data in ROAD_GRAPH.items():
        connection = RoadNetwork(
            camera_a=cam_a,
            camera_b=cam_b,
            distance_km=data.get('distance_km'),
            speed_limit_kmph=data.get('speed_limit_kmph'),
            road_type=data.get('road_type'),
            traffic_condition=data.get('traffic_condition'),
            lanes=data.get('lanes'),
            has_traffic_lights=data.get('has_traffic_lights'),
            typical_travel_time_min=data.get('typical_travel_time_min'),
        )
        db.add(connection)
        count += 1
    
    db.commit()
    return {"message": f"Seeded {count} road network connections"}
