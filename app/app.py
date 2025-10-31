import reflex as rx


def index() -> rx.Component:
    return rx.el.main(
        rx.el.div(
            rx.el.h1(
                "Environment is ready...",
                class_name="text-3xl font-semibold text-gray-800 mb-4",
            ),
            rx.el.p(
                "Keep prompting to build your app!", class_name="text-gray-600 mb-12"
            ),
            rx.el.a(
                rx.el.button(
                    "View Documentation",
                    rx.icon("arrow-right", class_name="ml-2", size=16),
                    class_name="bg-violet-500 text-white px-6 py-3 rounded-lg hover:bg-violet-600 transition-colors flex items-center font-medium",
                ),
                href="https://reflex.dev/docs/ai-builder/overview/best-practices/",
                target="_blank",
            ),
            rx.el.button(
                "Show Notification",
                on_click=rx.toast("Hello from the bot!"),
                class_name="bg-gray-200 text-gray-800 px-6 py-3 rounded-lg hover:bg-gray-300 transition-colors flex items-center font-medium mt-4",
            ),
            class_name="flex flex-col items-center justify-center text-center min-h-screen",
        ),
        class_name="font-['Inter'] bg-white",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index)