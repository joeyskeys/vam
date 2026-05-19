def _register_render_override(self):
    print('in register render override')
    self._deregister_render_override()
    renderer = omr.MRenderer.theRenderer()
    if renderer is None:
        return
    override_name = f'vamRenderOverride_{id(self)}'
    override = VamRenderOverride(override_name, self)
    try:
        renderer.registerOverride(override)
        self._render_override = override
    except Exception:
        self._render_override = None

def _deregister_render_override(self):
    override = self._render_override
    if override is None:
        return
    renderer = omr.MRenderer.theRenderer()
    if renderer is not None:
        try:
            renderer.deregisterOverride(override)
        except Exception:
            pass
    self._render_override = None


class VamGuidingLineOp(omr.MUserRenderOperation):
    def __init__(self, name, vc):
        super(VamGuidingLineOp, self).__init__(name)
        self.vam_context = vc

    def execute(self, draw_ctx):
        return True

    def hasUIDrawables(self):
        return True

    def addUIDrawables(self, draw_mgr, frame_ctx):
        vc = self.vam_context
        if vc is None:
            return

        state = vc.vam_core.get_current_state()
        axis = getattr(vc.vam_core, 'axis', 'none')
        if state not in ('translate', 'rotate', 'scale') or axis not in ('x', 'y', 'z'):
            return

        lines = vc.vam_core.get_axis_guide_lines()
        if not lines:
            return

        color = {
            'x': om.MColor((1.0, 0.1, 0.1, 0.85)),
            'y': om.MColor((0.2, 1.0, 0.2, 0.85)),
            'z': om.MColor((0.25, 0.45, 1.0, 0.85)),
        }.get(axis, om.MColor((1.0, 1.0, 0.0, 0.85)))

        draw_mgr.beginDrawable()
        try:
            try:
                draw_mgr.setColor(color)
                draw_mgr.setLineWidth(2.0)
                draw_mgr.setLineStyle(omr.MUIDrawManager.kSolid)
            except Exception:
                pass

            for p1, p2 in lines:
                draw_mgr.line(p1, p2)
        finally:
            draw_mgr.endDrawable()

