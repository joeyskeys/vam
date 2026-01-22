# -*- coding: utf-8 -*-

from utils import singleton


class StateMachine:
    """
    Generic declarative state machine.
    
    States and transitions are defined as configuration data.
    The machine dynamically creates trigger methods based on transition definitions.
    Callbacks can be specified for state entry/exit and transition events.
    
    Example usage:
        states = ['idle', 'running', 'stopped']
        transitions = [
            {'trigger': 'start', 'source': 'idle', 'dest': 'running', 'before': 'on_start'},
            {'trigger': 'stop', 'source': 'running', 'dest': 'stopped', 'after': 'on_stop'},
        ]
        
        machine = StateMachine(
            model=my_obj,
            states=states,
            transitions=transitions,
            initial='idle'
        )
        
        # Triggers become methods on the model
        my_obj.start()  # Transitions from idle to running
    """
    
    def __init__(self, model, states, transitions, initial='initial'):
        """
        Initialize state machine with declarative configuration.
        
        Args:
            model: Object that owns this state machine (callbacks are called on this object)
            states: List of state names (strings)
            transitions: List of transition dicts with keys:
                - trigger: Name of the trigger method to create
                - source: Source state name (or list of source states)
                - dest: Destination state name
                - before: (optional) Callback method name to call before transition
                - after: (optional) Callback method name to call after transition
            initial: Name of the initial state (default: 'initial')
        """
        self.model = model
        self.states = states
        self.transitions = transitions
        self.state = initial
        
        # Build transition lookup for quick access
        self._transition_map = {}
        for trans in transitions:
            trigger = trans['trigger']
            if trigger not in self._transition_map:
                self._transition_map[trigger] = []
            self._transition_map[trigger].append(trans)
        
        # Dynamically add trigger methods to the model
        for trigger in self._transition_map.keys():
            self._add_trigger(trigger)
        
        # Call on_enter for initial state
        self._call_state_callback('on_enter', initial)
    
    def _add_trigger(self, trigger_name):
        """
        Dynamically add a trigger method to the model.
        
        Args:
            trigger_name: Name of the trigger
        """
        def trigger_method(*args, **kwargs):
            return self._execute_trigger(trigger_name, *args, **kwargs)
        
        # Add method to model instance
        setattr(self.model, trigger_name, trigger_method)
    
    def _execute_trigger(self, trigger_name, *args, **kwargs):
        """
        Execute a trigger, causing a state transition if valid.
        
        Args:
            trigger_name: Name of the trigger to execute
            *args, **kwargs: Arguments passed to callback functions
        
        Returns:
            bool: True if transition occurred, False otherwise
        """
        if trigger_name not in self._transition_map:
            print(f"Warning: Trigger '{trigger_name}' not defined")
            return False
        
        # Find valid transition from current state
        valid_transition = None
        for trans in self._transition_map[trigger_name]:
            source = trans['source']
            # Support single source or list of sources
            sources = [source] if isinstance(source, str) else source
            
            if self.state in sources:
                valid_transition = trans
                break
        
        if not valid_transition:
            print(f"Cannot trigger '{trigger_name}' from state '{self.state}'")
            return False
        
        old_state = self.state
        new_state = valid_transition['dest']
        
        # Execute before callback if defined
        if 'before' in valid_transition:
            self._call_callback(valid_transition['before'], *args, **kwargs)
        
        # Exit old state
        self._call_state_callback('on_exit', old_state)
        
        # Change state
        self.state = new_state
        
        # Enter new state
        self._call_state_callback('on_enter', new_state)
        
        # Execute after callback if defined
        if 'after' in valid_transition:
            self._call_callback(valid_transition['after'], *args, **kwargs)
        
        return True
    
    def _call_callback(self, callback_name, *args, **kwargs):
        """
        Call a callback method on the model if it exists.
        
        Args:
            callback_name: Name of the callback method
            *args, **kwargs: Arguments to pass to callback
        """
        if hasattr(self.model, callback_name):
            callback = getattr(self.model, callback_name)
            if callable(callback):
                callback(*args, **kwargs)
    
    def _call_state_callback(self, callback_prefix, state_name):
        """
        Call a state-specific callback like on_enter_statename or on_exit_statename.
        
        Args:
            callback_prefix: 'on_enter' or 'on_exit'
            state_name: Name of the state
        """
        # Try specific callback like on_enter_normal
        specific_callback = f"{callback_prefix}_{state_name}"
        if hasattr(self.model, specific_callback):
            callback = getattr(self.model, specific_callback)
            if callable(callback):
                callback()
                return
        
        # Fall back to generic callback like on_enter with state as argument
        if hasattr(self.model, callback_prefix):
            callback = getattr(self.model, callback_prefix)
            if callable(callback):
                callback(state_name)
    
    def get_state(self):
        """Get the current state name."""
        return self.state
    
    def is_state(self, state_name):
        """
        Check if currently in a specific state.
        
        Args:
            state_name: State name to check
            
        Returns:
            bool: True if in that state
        """
        return self.state == state_name


@singleton
class VamCore:
    """
    Core singleton for VAM tool state management.
    
    Manages:
    - State machine with Normal, Moving, and RegisterPicking states
    - Shared transform settings (trs, axis, base)
    - Provides interface for state transitions
    
    States and transitions are defined declaratively.
    """
    
    # State definitions
    states = ['normal', 'moving', 'register_picking']
    
    # Transition definitions
    # Creates trigger methods: to_moving(), to_normal(), to_register_picking()
    transitions = [
        {'trigger': 'to_moving', 'source': 'normal', 'dest': 'moving', 'before': 'before_moving'},
        {'trigger': 'to_normal', 'source': ['moving', 'register_picking'], 'dest': 'normal', 'before': 'before_normal'},
        {'trigger': 'to_register_picking', 'source': 'normal', 'dest': 'register_picking'},
    ]
    
    # Available transform modes
    trs_modes = ['translate', 'rotate', 'scale']
    axes = ['none', 'x', 'y', 'z']
    bases = ['screen', 'local', 'world']
    
    def __init__(self):
        """Initialize VamCore with state machine and default settings."""
        # Transform settings - shared context across states
        self.trs = 'translate'
        self.axis = 'none'
        self.base = 'screen'
        
        # State-specific data
        self.moving_initial_values = {}
        
        # Initialize state machine with declarative configuration
        # This will automatically create to_moving(), to_normal(), etc. methods
        self.machine = StateMachine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial='normal'
        )
    
    # State lifecycle callbacks
    def on_enter_normal(self):
        """Called when entering normal state."""
        print("Entered NORMAL state - Selection mode active")
    
    def on_exit_normal(self):
        """Called when exiting normal state."""
        print("Exiting NORMAL state")
    
    def on_enter_moving(self):
        """Called when entering moving state."""
        print("Entered MOVING state - Transform mode active")
        # Store initial transform values for potential reset
        self.moving_initial_values = {}
    
    def on_exit_moving(self):
        """Called when exiting moving state."""
        print("Exiting MOVING state")
        # Commit or cancel transform changes
        self.moving_initial_values = {}
    
    def on_enter_register_picking(self):
        """Called when entering register picking state."""
        print("Entered REGISTER_PICKING state (not yet implemented)")
    
    def on_exit_register_picking(self):
        """Called when exiting register picking state."""
        print("Exiting REGISTER_PICKING state")
    
    # Transition callbacks
    def before_moving(self):
        """Called before transitioning to moving state."""
        print("Preparing to enter moving mode...")
    
    def before_normal(self):
        """Called before transitioning to normal state."""
        print("Returning to normal mode...")
    
    # Event handlers
    def handle_mouse_event(self, event):
        """
        Handle mouse events based on current state.
        
        Args:
            event: Mouse event from Maya context
        """
        current_state = self.machine.get_state()
        
        if current_state == 'normal':
            self._handle_mouse_normal(event)
        elif current_state == 'moving':
            self._handle_mouse_moving(event)
        elif current_state == 'register_picking':
            self._handle_mouse_register_picking(event)
    
    def handle_key_event(self, event):
        """
        Handle keyboard events based on current state.
        
        Args:
            event: Key event from Maya context
        """
        current_state = self.machine.get_state()
        
        if current_state == 'normal':
            self._handle_key_normal(event)
        elif current_state == 'moving':
            self._handle_key_moving(event)
        elif current_state == 'register_picking':
            self._handle_key_register_picking(event)
    
    def update(self):
        """Update current state."""
        current_state = self.machine.get_state()
        
        if current_state == 'normal':
            self._update_normal()
        elif current_state == 'moving':
            self._update_moving()
        elif current_state == 'register_picking':
            self._update_register_picking()
    
    # Normal state handlers
    def _handle_mouse_normal(self, event):
        """Handle mouse events in normal state."""
        # TODO: Implement controller selection logic
        pass
    
    def _handle_key_normal(self, event):
        """Handle keyboard events in normal state."""
        # TODO: Implement keyboard shortcuts for selection
        # TODO: Detect special keys that trigger Moving state transition
        # Example: if special_key_pressed: self.to_moving()
        pass
    
    def _update_normal(self):
        """Update normal state."""
        pass
    
    # Moving state handlers
    def _handle_mouse_moving(self, event):
        """Handle mouse events in moving state."""
        # TODO: Calculate transform based on mouse position and current settings
        # TODO: Apply transform preview (non-committed)
        pass
    
    def _handle_key_moving(self, event):
        """Handle keyboard events in moving state."""
        # TODO: Implement key mappings for transform parameters
        # TODO: Detect exit key to return to Normal state
        # Example: if escape_pressed: self.to_normal()
        pass
    
    def _update_moving(self):
        """Update moving state."""
        # TODO: Continuously update transform preview
        pass
    
    # Register picking state handlers (stubs)
    def _handle_mouse_register_picking(self, event):
        """Handle mouse events in register picking state."""
        pass
    
    def _handle_key_register_picking(self, event):
        """Handle keyboard events in register picking state."""
        pass
    
    def _update_register_picking(self):
        """Update register picking state."""
        pass
    
    # Query methods
    def get_current_state(self):
        """Get the name of the current state."""
        return self.machine.get_state()
    
    def is_normal(self):
        """Check if in normal state."""
        return self.machine.is_state('normal')
    
    def is_moving(self):
        """Check if in moving state."""
        return self.machine.is_state('moving')
    
    def is_register_picking(self):
        """Check if in register picking state."""
        return self.machine.is_state('register_picking')


if __name__ == '__main__':
    # Test the state machine
    vam_core = VamCore()
    print(f"Initial state: {vam_core.get_current_state()}")
    print()
    
    # Test transitions - these methods are created dynamically by StateMachine
    print("Testing transition to moving state:")
    vam_core.to_moving()
    print(f"Current state: {vam_core.get_current_state()}")
    print()
    
    print("Testing transition back to normal state:")
    vam_core.to_normal()
    print(f"Current state: {vam_core.get_current_state()}")
    print()
    
    # Test invalid transition
    print("Testing invalid transition (moving from normal to register_picking):")
    vam_core.to_register_picking()
    print(f"Current state: {vam_core.get_current_state()}")