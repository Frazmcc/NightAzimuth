from __future__ import annotations

from PIL import ImageTk

from .cloud_projection import CloudRegion, project_cloud_region
from .twilight_hud_finder_view import TwilightSmoothHudFinderView


class DirectionalCloudHudFinderView(TwilightSmoothHudFinderView):
    """Live finder with an optional indicative spatial cloud overlay."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._cloud_region: CloudRegion | None = None
        self._cloud_observer: tuple[float, float] | None = None
        self._show_cloud_overlay = False
        self._cloud_photo: ImageTk.PhotoImage | None = None
        super().__init__(*args, **kwargs)

    def set_cloud_overlay_enabled(self, enabled: bool) -> None:
        self._show_cloud_overlay = bool(enabled)
        self.redraw()

    def set_cloud_region(
        self,
        region: CloudRegion | None,
        *,
        observer_latitude: float | None = None,
        observer_longitude: float | None = None,
    ) -> None:
        self._cloud_region = region
        if region is None or observer_latitude is None or observer_longitude is None:
            self._cloud_observer = None
        else:
            self._cloud_observer = (float(observer_latitude), float(observer_longitude))
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        if not self._show_cloud_overlay or self._cloud_region is None or self._cloud_observer is None:
            self._cloud_photo = None
            return

        left, top, right, bottom = self._plot_bounds()
        width = max(1, int(right - left))
        height = max(1, int(bottom - top))
        latitude, longitude = self._cloud_observer
        texture = project_cloud_region(
            self._cloud_region,
            observer_latitude=latitude,
            observer_longitude=longitude,
            facing_deg=self.facing_deg,
            horizontal_fov_deg=self.horizontal_fov_deg,
            minimum_elevation_deg=self.minimum_elevation_deg,
            maximum_elevation_deg=self.maximum_elevation_deg,
            width=max(120, min(360, width // 2)),
            height=max(80, min(220, height // 2)),
        ).resize((width, height))
        self._cloud_photo = ImageTk.PhotoImage(texture)
        self.create_image(
            left,
            top,
            image=self._cloud_photo,
            anchor="nw",
            tags=("directional-cloud-overlay",),
        )
        self.tag_lower("directional-cloud-overlay")
