from kivy.app import App
from kivy.uix.spinner import Spinner
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Rectangle
from kivy.uix.popup import Popup
from kivy.uix.anchorlayout import AnchorLayout


from backend import load_graph, run_routing

# Global variables
from_address = ""
to_address = ""
priority_time = None
priority_distance = None
priority_bike_path = None
priority_protected_bike_path = None
priority_road_prioirty = None

class MyApp(App):
    def build(self):
        self.graph = load_graph()
        self.options = [
            "Time",
            "Distance",
            "Find Bike Lane",
            "Find Protected Bike Lane",
            "Road Priority"
        ]

        self.selected = [None] * 5
        self.spinners = []

        root = FloatLayout()

        # Background image
        bg_image = Image(source='slo.jpeg',
                         allow_stretch=True,
                         keep_ratio=False,
                         size_hint=(1, 1),
                         pos_hint={'x': 0, 'y': 0})
        root.add_widget(bg_image)

        # Top label
        top_label = Label(
            text="A* For Biking",
            size_hint=(1, None),
            height=50,
            pos_hint={'top': 1},
            color=(1, 1, 1, 1),
            bold=True,
            font_size='20sp',
        )

        with top_label.canvas.before:
            Color(0, 0, 0, 0.7)
            self.rect = Rectangle(size=top_label.size, pos=top_label.pos)

        def update_rect(instance, value):
            self.rect.pos = instance.pos
            self.rect.size = instance.size

        top_label.bind(pos=update_rect, size=update_rect)
        root.add_widget(top_label)

        # Main layout
        main_layout = BoxLayout(orientation='vertical',
                                spacing=10,
                                padding=(20, 80, 20, 20),
                                size_hint=(1, 1),
                                pos_hint={'x': 0, 'y': 0})
        root.add_widget(main_layout)

        for i in range(5):
            row = BoxLayout(orientation='horizontal',
                            size_hint_y=None,
                            height=40,
                            spacing=10)

            if i == 4:
                # Add the Reset button for Priority 5
                reset_button = Button(
                    text="Reset",
                    size_hint=(0.1, None),
                    size=(70, 40),
                    background_color=(1, 0.3, 0.3, 1)
                )
                reset_button.bind(on_press=self.reset_fields)
                row.add_widget(reset_button)  # Just add button, not row again
            else:
                # For alignment, add an invisible spacer
                row.add_widget(BoxLayout(size_hint_x=0.1))

            # Wrapper layout to center the label
            label_container = AnchorLayout(
                anchor_x='right', anchor_y='center',
                size_hint_x=0.4,  # keeps space for the label in the row
                width = 120
            )

            priority_label = Label(
                text=f"Priority {i + 1}",
                size_hint=(None, None),  # text only
                color=(0, 0, 0, 1),
                font_size=28
            )

            priority_label.bind(
                texture_size=lambda instance, value: setattr(instance, 'size', value)
            )

            # Create white background (this needs its own scope!)
            def add_background(label):
                with label.canvas.before:
                    Color(1, 1, 1, 0.8)
                    bg = Rectangle()

                def update_bg(instance, value):
                    bg.pos = instance.pos
                    bg.size = instance.size

                label.bind(pos=update_bg, size=update_bg)

            add_background(priority_label)

            label_container.add_widget(priority_label)
            row.add_widget(label_container)

            spinner = Spinner(
                text="Select",
                values=self.options[:],
                size_hint_x=0.2,
                background_color=(0.2, 0.4, 0.8, 1)
            )
            spinner.index = i
            spinner.bind(text=self.on_spinner_select)
            self.spinners.append(spinner)

            #row.add_widget(priority_label)
            row.add_widget(spinner)
            # Only add the row once, regardless of index
            main_layout.add_widget(row)

        self.top_text_input = TextInput(
            size_hint_y=None,
            height=50,
            multiline=False,
            hint_text="ENTER STARTING POINT RIGHT HERE"
        )
        main_layout.add_widget(self.top_text_input)

        self.text_input = TextInput(
            size_hint_y=None,
            height=50,
            multiline=False,
            hint_text="ENTER DESTINATION RIGHT HERE"
        )
        main_layout.add_widget(self.text_input)

        self.button = Button(
            text="Route",
            size_hint_y=None,
            height=50
        )
        self.button.bind(on_press=self.on_button_press)
        main_layout.add_widget(self.button)

        return root

    def reset_fields(self, instance):
        # Clear address inputs
        self.top_text_input.text = ""
        self.text_input.text = ""

        # Reset all spinners
        self.selected = [None] * 5
        for spinner in self.spinners:
            spinner.text = "Select"
            spinner.values = self.options[:]  # restore all options

    def on_spinner_select(self, spinner, text):
        index = spinner.index
        self.selected[index] = text if text != "Select" else None
        self.refresh_spinner_values()

    def refresh_spinner_values(self):
        used = set(sel for sel in self.selected if sel)

        for i, spinner in enumerate(self.spinners):
            current = self.selected[i]
            available = [opt for opt in self.options if opt not in used or opt == current]
            spinner.values = available

            if current not in available:
                self.selected[i] = None
                spinner.text = "Select"
            elif current:
                spinner.text = current

    def show_info(self, message):
        popup = Popup(
            title='Route Summary',
            content=Label(text=message),
            size_hint=(0.8, 0.4),
            auto_dismiss=True
        )
        popup.open()

    def on_button_press(self, instance):
        global from_address, to_address
        global priority_time, priority_distance, priority_bike_path
        global priority_protected_bike_path, priority_road_prioirty

        from_address = self.top_text_input.text.strip()
        to_address = self.text_input.text.strip()

        # Remove unwanted characters
        from_address = from_address.replace("\t", "").replace("\n", "")
        to_address = to_address.replace("\t", "").replace("\n", "")

        # Validate input
        if not from_address or not to_address:
            self.show_error("Please enter both a starting point and a destination.")
            return

            # Append city/state automatically
        suffix = ", San Luis Obispo, CA"
        from_address = from_address + suffix
        to_address = to_address + suffix

        print("From:", from_address)
        print("To:", to_address)
        print("Selected priorities in order:")
        for i, choice in enumerate(self.selected, 1):
            print(f"Priority {i}: {choice}")

        priority_map = {
            "Time": None,
            "Distance": None,
            "Find Bike Lane": None,
            "Find Protected Bike Lane": None,
            "Road Priority": None
        }

        for index, choice in enumerate(self.selected):
            if choice:
                priority_map[choice] = index + 1  # Priority level 1-5

        priority_time = priority_map["Time"]
        priority_distance = priority_map["Distance"]
        priority_bike_path = priority_map["Find Bike Lane"]
        priority_protected_bike_path = priority_map["Find Protected Bike Lane"]
        priority_road_priority = priority_map["Road Priority"]

        print("\nMapped Priorities:")
        print("Time:", priority_time)
        print("Distance:", priority_distance)
        print("Bike Lane:", priority_bike_path)
        print("Protected Bike Lane:", priority_protected_bike_path)
        print("Road Priority:", priority_road_priority)

        try:
            summary = run_routing(from_address, to_address, priority_map)

            message = (
                f"Distance: {summary['distance_m']:.0f} meters\n"
                f"Estimated Time: {summary['time_min']:.1f} minutes\n"
                f"Bike Lane Segments: {summary['bike_lane_segments']}\n"
                f"Protected Bike Segments: {summary['protected_segments']}\n\n"
                "Directions:\n" + "\n".join(summary['directions'])
            )
            self.show_info(message)

        except Exception as e:
            self.show_error(f"Routing error: {str(e)}")

    def show_error(self, message):
        popup = Popup(
            title='Error',
            content=Label(text=message),
            size_hint=(0.8, 0.3),
            auto_dismiss=True
        )
        popup.open()


if __name__ == '__main__':
    MyApp().run()