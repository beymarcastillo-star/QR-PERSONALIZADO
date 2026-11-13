from nicegui import ui, app
from sqlmodel import Session
from app.core.database import engine
from app.services.qr_renderer import COLOR_POR_DEFECTO, STYLES
from app.services.qr_service import QRService
from app.services.qr_shapes import SHAPES


def _descargar(url: str, nombre: str) -> None:
    """Descarga el PNG (compatible con distintas versiones de NiceGUI)."""
    if hasattr(ui.download, 'from_url'):
        ui.download.from_url(url, nombre)
    else:
        ui.download(url, nombre)


def render_dashboard():
    if not app.storage.user.get('authenticated', False):
        ui.navigate.to('/')
        return

    user_id = app.storage.user.get('user_id')
    username = app.storage.user.get('username')
    referencia = {'bytes': None, 'nombre': None}      # imagen de referencia opcional

    def logout():
        app.storage.user.clear()
        ui.navigate.to('/')

    with ui.header().classes('justify-between items-center bg-gray-800 text-white p-4 shadow'):
        ui.label(f'QRManager | Sesión: {username}').classes('text-lg font-bold')
        ui.button('Cerrar Sesión', on_click=logout).props('flat color=white')

    with ui.column().classes('w-full max-w-4xl mx-auto p-4 gap-4'):
        with ui.card().classes('w-full p-4'):
            ui.label('Generar Nuevo Código QR').classes('text-xl font-bold mb-2')
            with ui.row().classes('w-full gap-4'):
                title_input = ui.input('Título / Referencia').classes('flex-1')
                category_input = ui.select(['General', 'URL', 'WiFi', 'Contacto'], value='General').classes('w-32')
            content_input = ui.input('Contenido o URL del QR (ej. https://...)').classes('w-full mt-2')

            ui.label('Personalizar (opcional)').classes('text-md font-bold mt-3')
            with ui.row().classes('w-full gap-4 items-center'):
                style_select = ui.select(STYLES, value='cuadrado', label='Estilo de los puntos').classes('w-56')
                shape_select = ui.select(SHAPES, value='ninguna', label='Forma (gato, perrito, árbol...)').classes('w-64')
                color_input = ui.color_input('Color', value=COLOR_POR_DEFECTO).classes('w-40')
            ui.label('Los colores muy claros se oscurecen solos para que el QR se pueda escanear.') \
                .classes('text-xs text-gray-500')

            with ui.row().classes('w-full gap-4 items-center mt-2'):
                async def al_subir(e):
                    archivo = e.file if hasattr(e, 'file') else None
                    if archivo is not None:                       # NiceGUI 3 y 4
                        nombre, datos = archivo.name, await archivo.read()
                    else:                                         # NiceGUI 2
                        nombre, datos = e.name, e.content.read()
                    referencia['bytes'], referencia['nombre'] = datos, nombre
                    if getattr(e, 'sender', None) is not None:
                        e.sender.reset()                          # deja el cuadro listo para otra imagen
                    estado_img.text = f'Imagen de referencia: {nombre}'
                    ui.notify('Imagen cargada: el QR intentará imitarla', type='positive')

                ui.upload(label='Imagen de referencia (opcional)', auto_upload=True, on_upload=al_subir,
                          max_file_size=5_000_000,
                          on_rejected=lambda: ui.notify('No se pudo cargar la imagen (máximo 5 MB)', type='negative')) \
                    .props('accept=image/* flat bordered').classes('w-72')
                with ui.column().classes('gap-1'):
                    estado_img = ui.label('Sin imagen de referencia').classes('text-sm text-gray-600')

                    def quitar_imagen():
                        referencia['bytes'] = referencia['nombre'] = None
                        estado_img.text = 'Sin imagen de referencia'

                    ui.button('Quitar imagen', on_click=quitar_imagen).props('flat dense size=sm color=red')

            vista_previa = ui.image().classes('w-48 h-48 hidden')

            def opciones():
                return dict(style=style_select.value, shape=shape_select.value,
                            color=color_input.value or COLOR_POR_DEFECTO, ref_image=referencia['bytes'])

            def previsualizar():
                if not content_input.value:
                    ui.notify('Escriba el contenido del QR', type='warning')
                    return
                try:
                    vista_previa.set_source(QRService.preview_base64(content_input.value, **opciones()))
                    vista_previa.classes(remove='hidden')
                except ValueError as err:
                    ui.notify(str(err), type='negative')

            def create_qr():
                if not title_input.value or not content_input.value:
                    ui.notify('Complete el título y el contenido', type='warning')
                    return
                try:
                    with Session(engine) as session:
                        QRService(session).create_qr(title_input.value, content_input.value,
                                                     category_input.value, user_id, **opciones())
                except ValueError as err:
                    ui.notify(str(err), type='negative')
                    return
                title_input.value = ''
                content_input.value = ''
                vista_previa.classes(add='hidden')
                quitar_imagen()
                refresh_grid()
                ui.notify('Código QR generado con éxito', type='positive')

            with ui.row().classes('gap-3 mt-3'):
                ui.button('Vista previa', on_click=previsualizar).props('outline color=primary')
                ui.button('Generar y Guardar QR', on_click=create_qr).classes('bg-blue-600 text-white')

        ui.label('Mis Códigos QR Guardados').classes('text-xl font-bold mt-4')
        grid_container = ui.row().classes('w-full wrap gap-4')

        def refresh_grid():
            grid_container.clear()
            with Session(engine) as session:
                service = QRService(session)
                items = service.get_user_qrs(user_id)

            with grid_container:
                if not items:
                    ui.label('No hay códigos QR generados aún.').classes('text-gray-500 italic')
                for item in items:
                    with ui.card().classes('w-72 p-4 items-center shadow border'):
                        ui.label(item.title).classes('font-bold text-lg text-center truncate w-full')
                        with ui.row().classes('gap-1 mb-2'):
                            ui.badge(item.category)
                            if item.shape and item.shape != 'ninguna':
                                ui.badge(SHAPES.get(item.shape, item.shape)).props('color=purple')
                            if item.ref_image:
                                ui.badge('con imagen').props('color=teal')

                        if item.qr_file:
                            url = f'/qrs/{item.qr_file}'
                        else:                                     # registros antiguos
                            url = QRService.generate_qr_base64(item.data_content)
                        ui.image(url).classes('w-48 h-48 object-contain my-2')

                        ui.label(item.data_content).classes('text-xs text-gray-500 truncate w-full text-center mb-2')

                        with ui.row().classes('w-full justify-between items-center mt-2'):
                            ui.button('Descargar', on_click=lambda u=url, t=item.title: _descargar(u, f'{t}.png')) \
                                .props('flat sm color=primary')
                            ui.button(icon='delete', on_click=lambda i_id=item.id: delete_item(i_id)).props('flat sm color=red')

        def delete_item(item_id: int):
            with Session(engine) as session:
                QRService(session).remove_qr(item_id)
            refresh_grid()
            ui.notify('QR eliminado', type='info')

        refresh_grid()
