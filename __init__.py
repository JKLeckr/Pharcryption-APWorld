from dataclasses import dataclass
from typing import Any, ClassVar

from typing_extensions import override

from BaseClasses import CollectionState, Item, ItemClassification, Location, MultiWorld, Region
from worlds.AutoWorld import World

from .options import PharcryptionOptions

ID_OFFSET = 400_400_000


class PharcryptionItem(Item):
    game = "Pharcryption"


class PharcryptionLocation(Location):
    game = "Pharcryption"


@dataclass
class PharcryptionItemData:
    block: int
    cost: int

    def increase_cost(self):
        self.cost += 1


class PharcryptionWorld(World):
    """
    A cooperative meta-game for Archipelago where players must work together to mine Pharcoins to decrypt their items
    from a malevolent ransomware program.
    """
    game: ClassVar[str] = "Pharcryption"
    data_version: ClassVar[int] = 0
    options_dataclass = PharcryptionOptions
    options: PharcryptionOptions  # pyright: ignore[reportIncompatibleVariableOverride]
    item_name_to_id: ClassVar[dict[str, int]] = {
        "1 Pharcoin":     ID_OFFSET + 0,
        "2 Pharcoins":    ID_OFFSET + 1,
        "3 Pharcoins":    ID_OFFSET + 2,
        "4 Pharcoins":    ID_OFFSET + 3,
        "5 Pharcoins":    ID_OFFSET + 4,
        "Decryption Key": ID_OFFSET + 5,
        "Nothing":        ID_OFFSET + 6,
    }
    location_name_to_id: ClassVar[dict[str, int]] = {
        f"Encrypted Item {item_i + 1} in Block {block_i + 1}": ID_OFFSET + (100 * block_i) + item_i
        for item_i in range(100)
        for block_i in range(25)
    }

    required_server_version: tuple[int, int, int] = (0, 5, 0)

    # Pharcryption specific instance values.
    item_costs: dict[int, list[PharcryptionItemData]]
    total_item_cost: int

    @override
    @classmethod
    def stage_assert_generate(cls, multiworld: MultiWorld) -> None:
        # Only allow one Pharcryption world.
        if sum(game == "Pharcryption" for game in multiworld.game.values()) > 1:
            raise RuntimeError("Only one Pharcryption world is supported at this time.")

        # Ensure there is at least one other world (except for Archipelago) in addition to Pharcryption.
        if cls._count_partner_players(multiworld) < 1:
            raise RuntimeError("There must be at least one additional non-Pharcryption or non-Archipelago world.")

    @override
    def create_item(self, name: str) -> PharcryptionItem:
        return PharcryptionItem(name, ItemClassification.progression, self.item_name_to_id[name], self.player)

    @override
    def generate_early(self) -> None:
        # In real Pharcryption seeds, Pharcoins should be found by other players.
        # Solo generation is used by Archipelago's generic world tests and has no partner world to place them in.
        if self._count_partner_players(self.multiworld) > 0:
            for item in self.item_name_to_id.keys():
                self.options.non_local_items.value.add(item)

        # THIS CODE IS TERRIBLE, BUT IT DOES THE JOB
        number_of_blocks = self.options.number_of_item_blocks.value
        items_per_block = self.options.number_of_items_per_block.value
        maximum_item_cost = self.options.maximum_pharcoin_cost.value
        # self.total_item_cost = self.random.randint(
        #     items_per_block * number_of_blocks,  # Min
        #     items_per_block * number_of_blocks * maximum_item_cost   # Max
        # )
        self.total_item_cost = int(items_per_block * number_of_blocks * (maximum_item_cost + 1) / 2)

        item_cost_threshold = number_of_blocks * items_per_block
        max_item_costs: list[PharcryptionItemData] = []
        cur_item_costs: list[PharcryptionItemData] = [
            PharcryptionItemData(block, 1) for block in range(number_of_blocks) for _ in range(items_per_block)
        ]
        while item_cost_threshold < self.total_item_cost:
            random_data_index = self.random.randint(0, len(cur_item_costs) - 1)
            data = cur_item_costs[random_data_index]

            data.increase_cost()
            item_cost_threshold += 1
            if data.cost >= maximum_item_cost:
                max_item_costs.append(data)
                cur_item_costs.pop(random_data_index)

        self.item_costs = {}
        for data in [*max_item_costs, *cur_item_costs]:
            self.item_costs.setdefault(data.block, []).append(data)

    @override
    def create_items(self) -> None:
        partner_players = self._count_partner_players(self.multiworld)

        number_of_blocks = self.options.number_of_item_blocks.value
        number_of_items = self.options.number_of_items_per_block.value * number_of_blocks
        _maximum_item_cost = self.options.maximum_pharcoin_cost.value
        extra_pharcoins = self.options.extra_pharcoins_per_player.value * partner_players
        final_total_cost = self.total_item_cost + extra_pharcoins

        item_pool: list[PharcryptionItem] = [self.create_item("1 Pharcoin") for _ in range(number_of_items)]
        max_cost_item_pool: list[PharcryptionItem] = []
        current_point_threshold = number_of_items
        while current_point_threshold < final_total_cost:
            random_item_index = self.random.randint(0, len(item_pool) - 1)
            item = item_pool[random_item_index]

            # Increase item size.
            if item.code is None:
                item.code = 0
            item.code += 1
            if item.name == "1 Pharcoin":
                item.name = "2 Pharcoins"
            elif item.name == "2 Pharcoins":
                item.name = "3 Pharcoins"
            elif item.name == "3 Pharcoins":
                item.name = "4 Pharcoins"
            elif item.name == "4 Pharcoins":
                item.name = "5 Pharcoins"

            # Remove this item from our "increment" pool when an item reaches the maximum value.
            if item.name == "5 Pharcoins":
                max_cost_item_pool.append(item)
                item_pool.pop(random_item_index)

            # Increment Point Threshold
            current_point_threshold += 1

        # Add to item pool.
        self.multiworld.itempool += max_cost_item_pool
        self.multiworld.itempool += item_pool

    @override
    def create_regions(self) -> None:
        has_partner_players = self._count_partner_players(self.multiworld) > 0
        number_of_blocks = self.options.number_of_item_blocks.value
        number_of_items_per_block = self.options.number_of_items_per_block.value

        menu_region = Region("Menu", self.player, self.multiworld)
        previous_region = menu_region

        self.multiworld.regions.append(menu_region)
        block_coins = 0
        required_percentage = self.options.required_percentage_of_items_decrypted_for_block_unlock.value / 100
        for block in range(number_of_blocks):
            block_region = Region(f"Block {block + 1}", self.player, self.multiworld)
            block_coins += int(sum(d.cost for d in self.item_costs.get(block - 1, [])) * required_percentage)
            previous_region.connect(
                block_region,
                None,
                lambda state, b=block_coins:
                    not has_partner_players or self._get_pharcoin_count(state, self.player) >= b
            )

            locations: dict[str, int] = {}
            for item in range(number_of_items_per_block):
                location_name = f"Encrypted Item {item + 1} in Block {block + 1}"
                locations[location_name] = self.location_name_to_id[location_name]

            previous_region = block_region
            block_region.add_locations(locations)
            self.multiworld.regions.append(block_region)

    @override
    def set_rules(self) -> None:
        item_blocks = self.options.number_of_item_blocks.value
        encrypted_items = item_blocks * self.options.number_of_items_per_block.value
        partner_locations = sum(
            1 for location in self.multiworld.get_locations()
            if self.multiworld.game[location.player] not in {"Pharcryption", "Archipelago"}
        )
        if self._count_partner_players(self.multiworld) > 0 and partner_locations < encrypted_items:
            raise RuntimeError(
                "Pharcryption requires at least as many non-Pharcryption locations as encrypted items. "
                f"Found {partner_locations} non-Pharcryption locations for {encrypted_items} encrypted items."
            )

        # final_block = self.options.number_of_item_blocks.value - 1
        all_coins = 0
        for b in range(item_blocks):
            all_coins += sum(data.cost for data in self.item_costs[b])
        self.multiworld.completion_condition[self.player] = lambda state: (
            self._get_pharcoin_count(state, self.player) >= all_coins
        )

    @override
    def fill_slot_data(self) -> dict[str, Any]:
        use_time_limit = bool(self.options.enable_time_limit.value)
        slot_data: dict[str, Any] = {
            "percentage": self.options.required_percentage_of_items_decrypted_for_block_unlock.value,
            "password": self.options.starting_password.value,
            "timelimit": self.options.time_limit_in_minutes.value if use_time_limit else 0,
            "item_costs": {}
        }

        for block, _list in self.item_costs.items():
            slot_data["item_costs"][block] = {}
            for index, data in enumerate(_list, 0):
                location_id = ID_OFFSET + (block * 100) + index
                location_name = self.location_id_to_name[location_id]
                item = self.multiworld.get_location(location_name, self.player).item
                if item is None:
                    raise ValueError(f"item is none for location {location_name} ({location_id})")
                if item.code is None:
                    raise ValueError(f"item code is none for location {location_name} ({location_id})")
                slot_data["item_costs"][block][location_id] = {
                    "id": item.code,
                    "player": item.player,
                    "cost": data.cost,
                }

        return slot_data

    @staticmethod
    def _count_partner_players(multiworld: MultiWorld) -> int:
        return sum(
            game not in {"Pharcryption", "Archipelago"}
            for game in multiworld.game.values()
        )

    @staticmethod
    def _get_pharcoin_count(state: CollectionState, player: int) -> int:
        return state.count("1 Pharcoin", player) + \
               state.count("2 Pharcoins", player) * 2 + \
               state.count("3 Pharcoins", player) * 3 + \
               state.count("4 Pharcoins", player) * 4 + \
               state.count("5 Pharcoins", player) * 5
