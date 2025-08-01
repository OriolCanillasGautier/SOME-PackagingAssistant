import trimesh
import numpy as np

class CollisionManager:
    """
    A wrapper for trimesh.collision.CollisionManager to handle precise 
    collision checks between mesh objects within a container.
    """
    def __init__(self, container_mesh: trimesh.Trimesh):
        """
        Initializes the CollisionManager.

        Args:
            container_mesh (trimesh.Trimesh): The mesh of the container (bin).
                                              It's treated as a static obstacle.
        """
        if not isinstance(container_mesh, trimesh.Trimesh):
            raise TypeError("container_mesh must be a trimesh.Trimesh object.")
            
        self.manager = trimesh.collision.CollisionManager()
        self.container_mesh = container_mesh
        
        # We consider the container walls as obstacles.
        # For a simple box, we can add 6 planes representing the walls.
        # This is often more efficient than using the full container mesh for collision.
        min_b, max_b = self.container_mesh.bounds
        
        # Add container walls as static obstacles
        # Bottom
        self.manager.add_object('wall_bottom', trimesh.creation.box(bounds=[(min_b[0], min_b[1], min_b[2]-1), (max_b[0], max_b[1], min_b[2])]))
        # Top (optional, depending on whether items can stick out)
        # self.manager.add_object('wall_top', trimesh.creation.box(bounds=[(min_b[0], min_b[1], max_b[2]), (max_b[0], max_b[1], max_b[2]+1)]))
        # Back
        self.manager.add_object('wall_back', trimesh.creation.box(bounds=[(min_b[0], min_b[1]-1, min_b[2]), (max_b[0], min_b[1], max_b[2])]))
        # Front
        self.manager.add_object('wall_front', trimesh.creation.box(bounds=[(min_b[0], max_b[1], min_b[2]), (max_b[0], max_b[1]+1, max_b[2])]))
        # Left
        self.manager.add_object('wall_left', trimesh.creation.box(bounds=[(min_b[0]-1, min_b[1], min_b[2]), (min_b[0], max_b[1], max_b[2])]))
        # Right
        self.manager.add_object('wall_right', trimesh.creation.box(bounds=[(max_b[0], min_b[1], min_b[2]), (max_b[0]+1, max_b[1], max_b[2])]))

        self.placed_items = {}

    def add_item(self, item_name: str, item_mesh: trimesh.Trimesh, transform: np.ndarray = np.eye(4)):
        """
        Adds a new item to the collision manager.

        Args:
            item_name (str): A unique name for the item.
            item_mesh (trimesh.Trimesh): The mesh of the item.
            transform (np.ndarray, optional): The 4x4 transformation matrix for the
                                              item's initial position and orientation.
                                              Defaults to identity matrix.
        """
        if item_name in self.placed_items:
            raise ValueError(f"Item with name '{item_name}' already exists.")
        
        self.manager.add_object(name=item_name, mesh=item_mesh, transform=transform)
        self.placed_items[item_name] = {'mesh': item_mesh, 'transform': transform}
        # print(f"✅ Item '{item_name}' added to collision manager.") # Comentat per reduir verbositat

    def check_collision(self, item_mesh: trimesh.Trimesh, transform: np.ndarray) -> bool:
        """
        Checks if a mesh at a given transform collides with any existing object
        (including container walls and other placed items).

        Args:
            item_mesh (trimesh.Trimesh): The mesh to check.
            transform (np.ndarray): The 4x4 transformation matrix for the mesh's
                                    position and orientation.

        Returns:
            bool: True if a collision occurs, False otherwise.
        """
        is_collision, _ = self.manager.in_collision_single(
            mesh=item_mesh,
            transform=transform
        )
        return is_collision

    def get_placed_items(self):
        """
        Returns the dictionary of placed items.

        Returns:
            dict: A dictionary where keys are item names and values are dicts
                  containing the 'mesh' and 'transform'.
        """
        return self.placed_items

    def reset(self):
        """
        Removes all placed items from the manager, but keeps the container walls.
        """
        for name in list(self.placed_items.keys()):
            self.manager.remove_object(name)
        self.placed_items = {}
        print("🔄 Collision manager reset. Placed items cleared.")
