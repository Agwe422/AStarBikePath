from kivy.app import App
from kivy.uix.spinner import Spinner
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget


class MyApp(App):
    def build(self):
        self.options = [
            "Speed",
            "Reduce Distance",
            "Find Bike Path",
            "Find Protected Bike Path",
            "Minimize Slope"
        ]

        self.selected = [None] * 5
        self.spinners = []

        # Use FloatLayout to layer widgets
        root = FloatLayout()

        # Background image
        bg_image = Image(source='slo.jpeg',
                         allow_stretch=True,
                         keep_ratio=False,
                         size_hint=(1, 1),
                         pos_hint={'x': 0, 'y': 0})
        root.add_widget(bg_image)

        # Main layout on top
        main_layout = BoxLayout(orientation='vertical',
                                spacing=10,
                                padding=20,
                                size_hint=(1, 1),
                                pos_hint={'x': 0, 'y': 0})
        root.add_widget(main_layout)

        top_label = Label(text="A* For Biking", size_hint_y=None, height=40)
        main_layout.add_widget(top_label)

        for i in range(5):
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
            priority_label = Label(text=f"Priority {i+1}", size_hint_x=0.3)

            spinner = Spinner(
                text="Select",
                values=self.options[:],
                size_hint_x=0.7
            )

            spinner.index = i
            spinner.bind(text=self.on_spinner_select)
            self.spinners.append(spinner)

            row.add_widget(priority_label)
            row.add_widget(spinner)
            main_layout.add_widget(row)

        self.text_input = TextInput(
            size_hint_y=None,
            height=50,
            multiline=False,
            hint_text="Type something here"
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

    def on_button_press(self, instance):
        print("Selected priorities in order:")
        for i, choice in enumerate(self.selected, 1):
            print(f"Priority {i}: {choice}")
        instance.text = self.text_input.text


if __name__ == '__main__':
    MyApp().run()