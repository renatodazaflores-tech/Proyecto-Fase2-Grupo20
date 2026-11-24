import os

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash

st.set_page_config(
    page_title="Sistema de Reparaciones",
    layout="wide"
)

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

def consultar(sql, parametros=None):
    with engine.connect() as conexion:
        return pd.read_sql(
            text(sql), conexion, params=parametros
        )

if "usuario" not in st.session_state:
    st.session_state.usuario = None

if st.session_state.usuario is None:

    st.title("Sistema Integral de Reparaciones")
    st.subheader("Inicio de sesión - Grupo 20")

    with st.form("login"):
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        ingresar = st.form_submit_button("Ingresar")

    if ingresar:
        resultado = consultar("""
            SELECT u.cuenta_usuario,
                   u.nombre_usuario,
                   u.password_hash,
                   r.nombre_rol
            FROM usuario u, usuario_rol r
            WHERE u.cuenta_usuario = r.cuenta_usuario
            AND u.cuenta_usuario = :usuario
            AND u.activo = 1
        """, {"usuario": usuario})

        if not resultado.empty:
            fila = resultado.iloc[0]

            if fila["password_hash"] and check_password_hash(
                fila["password_hash"], clave
            ):
                st.session_state.usuario = usuario
                st.session_state.nombre = fila["nombre_usuario"]
                st.session_state.rol = fila["nombre_rol"]
                st.rerun()

        st.error("Usuario o contraseña incorrectos")

    st.stop()

st.sidebar.title("Grupo 20")
st.sidebar.write(st.session_state.nombre)
st.sidebar.write("Rol:", st.session_state.rol)

if st.sidebar.button("Cerrar sesión"):
    st.session_state.clear()
    st.rerun()

st.title("Sistema Integral de Reparaciones")

if st.session_state.rol == "Administrador":
    st.success("Acceso de administrador")
else:
    st.info("Acceso de operador")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Clientes", consultar(
    "SELECT COUNT(*) FROM cliente").iloc[0,0])

col2.metric("Equipos", consultar(
    "SELECT COUNT(*) FROM equipo").iloc[0,0])

col3.metric("Ordenes", consultar(
    "SELECT COUNT(*) FROM orden").iloc[0,0])

col4.metric("Sucursales", consultar(
    "SELECT COUNT(*) FROM sucursal").iloc[0,0])

st.subheader("Sucursales registradas")
st.dataframe(consultar("SELECT * FROM sucursal"))

st.divider()
st.header("Ingreso de órdenes de reparación")

clientes = consultar("""
    SELECT rut_cliente, nombre
    FROM cliente
    WHERE activo = 1
""")

equipos = consultar("""
    SELECT codigo_interno, marca, modelo
    FROM equipo
    WHERE activo = 1
""")

sucursales = consultar("""
    SELECT codigo, nombre_sucursal
    FROM sucursal
    WHERE activo = 1
""")

with st.form("nueva_orden"):

    cliente = st.selectbox(
        "Cliente",
        clientes["rut_cliente"],
        format_func=lambda x: x + " - " +
        clientes.loc[clientes.rut_cliente == x,
                     "nombre"].iloc[0]
    )

    equipo = st.selectbox(
        "Equipo",
        equipos["codigo_interno"],
        format_func=lambda x: x + " - " +
        equipos.loc[equipos.codigo_interno == x,
                    "marca"].iloc[0]
    )

    sucursal = st.selectbox(
        "Sucursal",
        sucursales["codigo"],
        format_func=lambda x:
        sucursales.loc[sucursales.codigo == x,
                       "nombre_sucursal"].iloc[0]
    )

    recepcion = st.date_input("Fecha de recepción")
    comprometida = st.date_input("Fecha comprometida")
    problema = st.text_area("Problema informado", max_chars=255)

    guardar = st.form_submit_button("Registrar orden")

if guardar:
    if not problema.strip():
        st.error("Debe ingresar el problema informado")

    elif comprometida < recepcion:
        st.error("La fecha comprometida no puede ser anterior a la recepción")

    else:
        try:
            with engine.begin() as conexion:

                numero = conexion.execute(text("""
                    SELECT COALESCE(MAX(numero_orden), 0) + 1
                    FROM orden
                """)).scalar()

                conexion.execute(text("""
                    INSERT INTO orden
                    (numero_orden, codigo_sucursal,
                     rut_cliente, codigo_interno_equipo,
                     fecha_recepcion, fecha_comprometida,
                     problema_informado, estado_actual)
                    VALUES
                    (:numero, :sucursal, :cliente,
                     :equipo, :recepcion, :comprometida,
                     :problema, 'Pendiente')
                """), {
                    "numero": numero,
                    "sucursal": sucursal,
                    "cliente": cliente,
                    "equipo": equipo,
                    "recepcion": recepcion,
                    "comprometida": comprometida,
                    "problema": problema.strip()
                })

            st.success(f"Orden {numero} registrada correctamente")

        except Exception:
            st.error("No se pudo registrar la orden")

st.subheader("Últimas órdenes registradas")

st.dataframe(consultar("""
    SELECT numero_orden, rut_cliente,
           codigo_interno_equipo,
           fecha_recepcion, estado_actual
    FROM orden
    ORDER BY numero_orden DESC
    LIMIT 10
"""))

if st.session_state.rol == "Administrador":

    st.divider()
    st.header("Administración de registros")

    tabla = st.selectbox(
        "Tabla que desea administrar",
        ["cliente", "equipo"]
    )

    accion = st.radio(
        "Operación",
        ["Consultar", "Agregar", "Modificar", "Desactivar"],
        horizontal=True
    )

    def ejecutar(sql, parametros):
        try:
            with engine.begin() as conexion:
                conexion.execute(text(sql), parametros)
            st.success("Operación realizada correctamente")
        except Exception:
            st.error("No se pudo realizar la operación")

    if accion == "Consultar":
        st.dataframe(consultar("SELECT * FROM " + tabla))

    elif tabla == "cliente":

        if accion == "Agregar":

            with st.form("agregar_cliente"):
                rut = st.text_input("RUT", max_chars=15)
                nombre = st.text_input("Nombre", max_chars=120)
                correo = st.text_input("Correo", max_chars=120)
                clasificacion = st.text_input("Clasificación", max_chars=40)

                if st.form_submit_button("Guardar cliente"):
                    if rut.strip() and nombre.strip():
                        ejecutar("""
                            INSERT INTO cliente
                            (rut_cliente, nombre,
                             correo_electronico, clasificacion, activo)
                            VALUES
                            (:rut, :nombre, :correo, :clasificacion, 1)
                        """, {
                            "rut": rut.strip(),
                            "nombre": nombre.strip(),
                            "correo": correo,
                            "clasificacion": clasificacion
                        })
                    else:
                        st.error("Complete los campos obligatorios")

        else:

            registros = consultar("""
                SELECT * FROM cliente WHERE activo = 1
            """)

            if not registros.empty:
                rut = st.selectbox(
                    "Seleccionar cliente",
                    registros["rut_cliente"]
                )

                fila = registros[
                    registros.rut_cliente == rut
                ].iloc[0]

                if accion == "Modificar":

                    with st.form("modificar_cliente"):
                        nombre = st.text_input(
                            "Nombre", value=fila["nombre"]
                        )
                        correo = st.text_input(
                            "Correo", value=fila["correo_electronico"] or ""
                        )
                        clasificacion = st.text_input(
                            "Clasificación", value=fila["clasificacion"] or ""
                        )

                        if st.form_submit_button("Guardar cambios"):
                            if nombre.strip():
                                ejecutar("""
                                    UPDATE cliente
                                    SET nombre = :nombre,
                                        correo_electronico = :correo,
                                        clasificacion = :clasificacion
                                    WHERE rut_cliente = :rut
                                """, {
                                    "nombre": nombre,
                                    "correo": correo,
                                    "clasificacion": clasificacion,
                                    "rut": rut
                                })
                            else:
                                st.error("Ingrese un nombre")

                elif accion == "Desactivar":

                    confirmar = st.checkbox("Confirmar desactivación")

                    if st.button("Desactivar cliente", disabled=not confirmar):
                        ejecutar("""
                            UPDATE cliente
                            SET activo = 0
                            WHERE rut_cliente = :rut
                        """, {"rut": rut})

    elif tabla == "equipo":

        if accion == "Agregar":

            with st.form("agregar_equipo"):
                codigo = st.text_input("Código interno", max_chars=30)
                marca = st.text_input("Marca", max_chars=60)
                modelo = st.text_input("Modelo", max_chars=80)
                serie = st.text_input("Número de serie", max_chars=80)
                compra = st.date_input("Fecha de compra")
                estado = st.selectbox(
                    "Estado de conservación",
                    ["Bueno", "Regular", "Malo"]
                )

                if st.form_submit_button("Guardar equipo"):
                    if codigo.strip() and marca.strip() and modelo.strip():
                        ejecutar("""
                            INSERT INTO equipo
                            (codigo_interno, tipo_equipo,
                             marca, modelo, numero_serie,
                             fecha_compra, estado_conservacion, activo)
                            VALUES
                            (:codigo, 'sin_clasificar',
                             :marca, :modelo, :serie,
                             :compra, :estado, 1)
                        """, {
                            "codigo": codigo,
                            "marca": marca,
                            "modelo": modelo,
                            "serie": serie,
                            "compra": compra,
                            "estado": estado
                        })
                    else:
                        st.error("Complete los campos obligatorios")

        else:

            registros = consultar("""
                SELECT * FROM equipo WHERE activo = 1
            """)

            if not registros.empty:
                codigo = st.selectbox(
                    "Seleccionar equipo",
                    registros["codigo_interno"]
                )

                fila = registros[
                    registros.codigo_interno == codigo
                ].iloc[0]

                if accion == "Modificar":

                    with st.form("modificar_equipo"):
                        marca = st.text_input(
                            "Marca", value=fila["marca"] or ""
                        )
                        modelo = st.text_input(
                            "Modelo", value=fila["modelo"] or ""
                        )
                        estado = st.text_input(
                            "Estado", value=fila["estado_conservacion"] or ""
                        )

                        if st.form_submit_button("Guardar cambios"):
                            if marca.strip() and modelo.strip():
                                ejecutar("""
                                    UPDATE equipo
                                    SET marca = :marca,
                                        modelo = :modelo,
                                        estado_conservacion = :estado
                                    WHERE codigo_interno = :codigo
                                """, {
                                    "marca": marca,
                                    "modelo": modelo,
                                    "estado": estado,
                                    "codigo": codigo
                                })
                            else:
                                st.error("Complete marca y modelo")

                elif accion == "Desactivar":

                    confirmar = st.checkbox("Confirmar desactivación")

                    if st.button("Desactivar equipo", disabled=not confirmar):
                        ejecutar("""
                            UPDATE equipo
                            SET activo = 0
                            WHERE codigo_interno = :codigo
                        """, {"codigo": codigo})

from datetime import date
import plotly.express as px

st.divider()
st.header("Dashboard de reparaciones")

sucursales = consultar("""
    SELECT nombre_sucursal
    FROM sucursal
    ORDER BY nombre_sucursal
""")

col1, col2, col3, col4 = st.columns(4)

inicio = col1.date_input(
    "Desde", value=date(2026, 1, 1),
    key="dash_inicio"
)

fin = col2.date_input(
    "Hasta", value=date(2026, 12, 31),
    key="dash_fin"
)

sucursal = col3.selectbox(
    "Sucursal",
    ["Todas"] + sucursales["nombre_sucursal"].tolist()
)

tipo = col4.selectbox(
    "Tipo de equipo",
    ["Todos", "computador", "telefono_movil",
     "tablet", "sin_clasificar"]
)

if inicio > fin:
    st.error("El rango de fechas no es válido.")
    st.stop()

datos = consultar("""
    SELECT o.numero_orden,
           o.fecha_recepcion,
           s.nombre_sucursal,
           e.tipo_equipo,
           e.codigo_interno,
           c.nombre AS cliente,
           COALESCE((
               SELECT SUM(i.costo_mano_obra)
               FROM intervencion_tecnica i
               WHERE i.numero_orden = o.numero_orden
           ), 0)
           +
           COALESCE((
               SELECT SUM(d.cantidad * d.precio_aplicado)
               FROM detalle_repuesto d
               WHERE d.numero_orden = o.numero_orden
           ), 0) AS costo_total,
           (
               SELECT AVG(ev.nota)
               FROM evaluacion ev
               WHERE ev.numero_orden = o.numero_orden
           ) AS nota,
           (
               SELECT AVG(ev.cumplimiento_plazo)
               FROM evaluacion ev
               WHERE ev.numero_orden = o.numero_orden
           ) AS cumplimiento
    FROM orden o, sucursal s, equipo e, cliente c
    WHERE o.codigo_sucursal = s.codigo
    AND o.codigo_interno_equipo = e.codigo_interno
    AND o.rut_cliente = c.rut_cliente
""")

datos["fecha_recepcion"] = pd.to_datetime(
    datos["fecha_recepcion"]
).dt.date

datos = datos[
    (datos["fecha_recepcion"] >= inicio) &
    (datos["fecha_recepcion"] <= fin)
]

if sucursal != "Todas":
    datos = datos[datos["nombre_sucursal"] == sucursal]

ranking = datos.copy()

if tipo != "Todos":
    ranking = ranking[ranking["tipo_equipo"] == tipo]

# GRAFICO 1

st.subheader("1. Equipos con mayor cantidad de órdenes")

g1 = ranking.groupby("tipo_equipo").size().reset_index(
    name="cantidad"
)

g1 = g1.sort_values("cantidad", ascending=False)

st.plotly_chart(px.bar(
    g1,
    x="tipo_equipo",
    y="cantidad",
    color="tipo_equipo",
    text_auto=True
), use_container_width=True)

# GRAFICO 2

st.subheader("2. Porcentaje de equipos por sucursal")

g2 = datos.groupby(
    ["nombre_sucursal", "tipo_equipo"]
).size().reset_index(name="cantidad")

g2["porcentaje"] = (
    g2["cantidad"] /
    g2.groupby("nombre_sucursal")["cantidad"].transform("sum")
) * 100

g2 = g2[g2["tipo_equipo"].isin(
    ["computador", "telefono_movil", "tablet"]
)]

st.plotly_chart(px.bar(
    g2,
    x="nombre_sucursal",
    y="porcentaje",
    color="tipo_equipo",
    barmode="group"
), use_container_width=True)

# GRAFICO 3

st.subheader("3. Relación entre costo y evaluación")

g3 = datos.dropna(subset=["nota"]).copy()

st.plotly_chart(px.scatter(
    g3,
    x="costo_total",
    y="nota",
    color="tipo_equipo",
    hover_data=[
        "numero_orden",
        "cliente",
        "codigo_interno",
        "nombre_sucursal"
    ]
), use_container_width=True)

st.dataframe(g3[[
    "numero_orden",
    "cliente",
    "codigo_interno",
    "nombre_sucursal",
    "costo_total",
    "nota"
]])

# GRAFICO 4

st.subheader("4. Cumplimiento de plazos por sucursal")

g4 = datos.dropna(subset=["cumplimiento"]).groupby(
    "nombre_sucursal"
)["cumplimiento"].mean().reset_index()

g4["porcentaje"] = g4["cumplimiento"] * 100

g4 = g4.sort_values("porcentaje")

st.plotly_chart(px.bar(
    g4,
    x="nombre_sucursal",
    y="porcentaje",
    color="porcentaje",
    text_auto=".1f"
), use_container_width=True)

st.caption(
    "Porcentaje de cumplimiento según las órdenes evaluadas."
)
