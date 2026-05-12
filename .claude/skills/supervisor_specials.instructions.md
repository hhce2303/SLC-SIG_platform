---
description: This instruction file provides guidelines for managing supervisor roles and handling SQL queries related to supervisors specials in the database.
applyTo: '**/*.sql, **/*.py'

# applyTo: 'Describe when these instructions should be loaded by the agent based on task context' # when provided, instructions will automatically be added to the request context when the pattern matches an attached file
---
instructions:
- When managing supervisors roles, ensure that you usea the right SQL queries to retrieve and update supervisor information in the database.
- Always verify the identity and permissions of supervisors before granting access to sensitive information or functionalities.

# def load_specials_by_supervisor(id_supervisor, status_filter):
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        sql = """
            SELECT 
                ds.ID_special, 
                ds.spec_datetime, 
                ds.ID_site, 
                s.site_name,
                a.act_name, 
                ds.spec_quantity, 
                ds.spec_camera,
                ds.spec_description, 
                ds.ID_user,
                s.site_timezone,
                ds.spec_status, 
                ds.spec_marked_by
            FROM daily_specials ds
            LEFT JOIN daily_sites s ON ds.ID_site = s.ID_site
            LEFT JOIN daily_activities a ON ds.ID_activity = a.ID_activity
            WHERE ds.ID_supervisor = %s
            AND (ds.spec_status IS NULL OR ds.spec_status != %s)
            ORDER BY ds.spec_datetime DESC
        """
        cur.execute(sql, (id_supervisor, status_filter))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[ERROR] load_specials_by_supervisor: {e}")
        import traceback
        traceback.print_exc()
        return []

# def update_special_status(special_id, status, marked_by):
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        if status is None:
            # Desmarcar
            cur.execute("""
                UPDATE daily_specials 
                SET spec_status = NULL, spec_marked_at = NULL, spec_marked_by = NULL
                WHERE ID_special = %s
            """, (special_id,))
        else:
            # Marcar con estado
            cur.execute("""
                UPDATE daily_specials 
                SET spec_status = %s, spec_marked_at = NOW(), spec_marked_by = %s
                WHERE ID_special = %s
            """, (status, marked_by, special_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] specials_model.update_special_status: {e}")
        import traceback
        traceback.print_exc()
        return False


# Covertidor de horarios a timezone del sitio, primero como se obtiene los timezones de los sitios y sus offsets:


 # def get_site_time_zone(site_id):   
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT site_timezone 
            FROM daily_sites 
            WHERE ID_site = %s
        """, (site_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else None
        
    except Exception as e:
        print(f"[ERROR] get_site_time_zone: {e}")
        return None
    
# def get_active_season():
    """
    Obtiene el season actualmente activo desde daily_season_offsets.
    
    Returns:
        str: Nombre del season activo ('winter', 'summer', etc.)
        None: Si no hay season activo o error
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT season_offsets
            FROM daily_season_offsets
            WHERE active = 1
            LIMIT 1
        """)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            season = result[0]
            print(f"[HELPER] 🌐 Season activo: {season}")
            return season
        else:
            print(f"[HELPER] ⚠️ No hay season activo configurado")
            return None
            
    except Exception as e:
        print(f"[HELPER] ❌ Error obteniendo season activo: {e}")
        return None


# def get_active_season_timezones():
    """
    Obtiene los timezone offsets según el season activo.
    Consulta automáticamente la tabla correcta (winter/summer).
    
    Returns:
        dict: {timezone_name: offset_hours}
        None: Si no hay season activo o error
    """
    try:
        # Obtener season activo
        active_season = get_active_season()
        
        if not active_season:
            print(f"[HELPER] ⚠️ No se puede obtener timezones sin season activo")
            return None
        
        # Determinar tabla según season
        if active_season.lower() == 'winter':
            table_name = 'daily_winter_offsets'
        elif active_season.lower() == 'summer':
            table_name = 'daily_summer_offsets'
        else:
            print(f"[HELPER] ⚠️ Season desconocido: {active_season}")
            return None
        
        # Consultar offsets desde la tabla correspondiente
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT time_zone, time_offset 
            FROM {table_name}
        """)
        
        timezones = {}
        for tz, offset in cursor.fetchall():
            timezones[tz] = offset
        
        cursor.close()
        conn.close()
        
        print(f"[HELPER] 🌐 Timezones cargados para season '{active_season}': {len(timezones)} zonas")
        return timezones