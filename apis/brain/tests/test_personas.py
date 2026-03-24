from app.services.personas import route_persona


class TestPersonaRouting:
    def test_engineering_keywords(self):
        assert route_persona("deploy the API to render") == "engineering"
        assert route_persona("the build is broken") == "engineering"

    def test_cfo_keywords(self):
        assert route_persona("how much have we spent?") == "cfo"
        assert route_persona("what's the monthly cost?") == "cfo"

    def test_ea_default(self):
        assert route_persona("hey there") == "ea"
        assert route_persona("random question") == "ea"

    def test_ea_explicit(self):
        assert route_persona("what should I work on today?") == "ea"

    def test_channel_override(self):
        assert route_persona("something", channel_id="C0ALLEKR9FZ") == "engineering"
        assert route_persona("something", channel_id="C0AM2310P8A") == "strategy"

    def test_parent_persona_override(self):
        assert route_persona("deploy stuff", parent_persona="legal") == "legal"

    def test_tax_keywords(self):
        assert route_persona("what are the IRS filing deadlines?") == "tax-domain"

    def test_growth_keywords(self):
        assert route_persona("we need better SEO for the landing page") == "growth"
